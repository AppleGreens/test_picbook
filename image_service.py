import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv()


class ImageServiceError(RuntimeError):
    """Raised when image generation cannot be completed."""


@dataclass(frozen=True)
class ImageResult:
    image_bytes: bytes
    image_url: str | None
    raw_response: dict[str, Any]


class NanoBananaImageService:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_wait_seconds: int | None = None,
        poll_interval_seconds: float | None = None,
        request_timeout_seconds: int | None = None,
    ) -> None:
        self.api_key = (
            api_key or os.getenv("NANO_BANANA_API_KEY") or os.getenv("GRSAI_API_KEY")
        )
        if not self.api_key:
            raise ImageServiceError("请先在 .env 中配置 NANO_BANANA_API_KEY。")

        self.base_url = (
            base_url or os.getenv("NANO_BANANA_BASE_URL", "https://api.grsai.com")
        ).rstrip("/")
        self.model = model or os.getenv("NANO_BANANA_MODEL", "nano-banana-pro")
        self.max_wait_seconds = max_wait_seconds or int(
            os.getenv("NANO_BANANA_MAX_WAIT_SECONDS", "120")
        )
        self.poll_interval_seconds = poll_interval_seconds or float(
            os.getenv("NANO_BANANA_POLL_INTERVAL_SECONDS", "5")
        )
        self.request_timeout_seconds = request_timeout_seconds or int(
            os.getenv("NANO_BANANA_REQUEST_TIMEOUT_SECONDS", "30")
        )

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        image_size: str = "2k",
    ) -> ImageResult:
        task_id, initial_response = self.start_generation(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )

        if self._is_succeeded(initial_response) and self._has_image(initial_response):
            return self._build_image_result(initial_response)

        final_response = self.wait_for_result(task_id)
        return self._build_image_result(final_response)

    def start_generation(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        image_size: str = "2k",
    ) -> tuple[str, dict[str, Any]]:
        if not prompt or not prompt.strip():
            raise ImageServiceError("请先输入一段绘本画面描述。")

        payload = {
            "model": self.model,
            "prompt": prompt.strip(),
            "aspectRatio": aspect_ratio,
            "imageSize": image_size,
            "webHook": "-1",
        }
        response = self._post("/v1/draw/nano-banana", payload)
        task_id = self._extract_task_id(response)
        if not task_id:
            raise ImageServiceError(f"提交绘画任务成功，但未返回任务 ID：{response}")

        return task_id, response

    def wait_for_result(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.max_wait_seconds

        while True:
            response = self._post("/v1/draw/result", {"id": task_id})
            if self._is_succeeded(response):
                return response

            if self._is_failed(response):
                raise ImageServiceError(self._extract_error_message(response))

            if time.monotonic() >= deadline:
                raise ImageServiceError(
                    f"图片生成超时，请稍后重试。任务 ID：{task_id}"
                )

            time.sleep(self.poll_interval_seconds)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.request_timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 403 and "cloudflare" in error_body.lower():
                raise ImageServiceError(
                    "图片服务请求被 Cloudflare 拦截。请将 "
                    "NANO_BANANA_BASE_URL 配置为 API 域名，例如 "
                    "https://api.grsai.com。"
                ) from exc
            raise ImageServiceError(
                f"图片服务请求失败（HTTP {exc.code}）：{error_body}"
            ) from exc
        except URLError as exc:
            raise ImageServiceError(f"无法连接图片服务：{exc.reason}") from exc

        if not raw_body:
            return {}

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ImageServiceError(f"图片服务返回了非 JSON 内容：{raw_body}") from exc

        if not isinstance(data, dict):
            raise ImageServiceError(f"图片服务返回格式不正确：{data}")

        code = data.get("code")
        if code not in (None, 0, "0"):
            raise ImageServiceError(self._extract_error_message(data))

        if data.get("success") is False:
            raise ImageServiceError(self._extract_error_message(data))

        return data

    def _build_image_result(self, response: dict[str, Any]) -> ImageResult:
        image_url = self._extract_image_url(response)
        image_base64 = self._extract_image_base64(response)

        if image_base64:
            return ImageResult(
                image_bytes=base64.b64decode(image_base64),
                image_url=None,
                raw_response=response,
            )

        if image_url:
            return ImageResult(
                image_bytes=self._download_image(image_url),
                image_url=image_url,
                raw_response=response,
            )

        raise ImageServiceError(f"图片生成成功，但未找到图片 URL 或图片数据：{response}")

    def _download_image(self, image_url: str) -> bytes:
        try:
            with urlopen(image_url, timeout=self.request_timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise ImageServiceError(
                f"下载生成图片失败（HTTP {exc.code}）：{error_body}"
            ) from exc
        except URLError as exc:
            raise ImageServiceError(f"下载生成图片失败：{exc.reason}") from exc

    def _payload_data(self, response: dict[str, Any]) -> dict[str, Any]:
        data = response.get("data")
        return data if isinstance(data, dict) else response

    def _extract_task_id(self, response: dict[str, Any]) -> str | None:
        data = self._payload_data(response)
        for container in (data, response):
            for key in ("id", "taskId", "task_id"):
                value = container.get(key)
                if value:
                    return str(value)
        return None

    def _is_succeeded(self, response: dict[str, Any]) -> bool:
        status = self._status(response)
        return status in {"succeeded", "success", "completed", "complete", "done"}

    def _is_failed(self, response: dict[str, Any]) -> bool:
        status = self._status(response)
        return status in {"failed", "failure", "error", "canceled", "cancelled"}

    def _status(self, response: dict[str, Any]) -> str:
        data = self._payload_data(response)
        return str(data.get("status") or response.get("status") or "").lower()

    def _has_image(self, response: dict[str, Any]) -> bool:
        return bool(
            self._extract_image_url(response) or self._extract_image_base64(response)
        )

    def _extract_image_url(self, response: dict[str, Any]) -> str | None:
        data = self._payload_data(response)

        for container in (data, response):
            for key in ("url", "imageUrl", "image_url"):
                value = container.get(key)
                if isinstance(value, str) and value:
                    return value

            for key in ("imageUrls", "image_urls"):
                value = container.get(key)
                if isinstance(value, list) and value:
                    first_url = value[0]
                    if isinstance(first_url, str) and first_url:
                        return first_url

        for key in ("results", "images", "output"):
            value = data.get(key) or response.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item:
                        return item
                    if isinstance(item, dict):
                        for image_key in ("url", "imageUrl", "image_url"):
                            image_url = item.get(image_key)
                            if isinstance(image_url, str) and image_url:
                                return image_url

        return None

    def _extract_image_base64(self, response: dict[str, Any]) -> str | None:
        data = self._payload_data(response)

        for container in (data, response):
            for key in ("b64_json", "base64", "imageBase64", "image_base64"):
                value = container.get(key)
                if isinstance(value, str) and value:
                    return value

        for key in ("results", "images", "output"):
            value = data.get(key) or response.get(key)
            if isinstance(value, list):
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    for image_key in (
                        "b64_json",
                        "base64",
                        "imageBase64",
                        "image_base64",
                    ):
                        image_base64 = item.get(image_key)
                        if isinstance(image_base64, str) and image_base64:
                            return image_base64

        return None

    def _extract_error_message(self, response: dict[str, Any]) -> str:
        data = self._payload_data(response)
        for container in (data, response):
            for key in ("failure_reason", "error", "message", "msg"):
                value = container.get(key)
                if value:
                    return f"图片生成失败：{value}"
        return f"图片生成失败：{response}"
