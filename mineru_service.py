import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


load_dotenv()


class MinerUServiceError(RuntimeError):
    """Raised when MinerU document parsing fails."""


class MinerUOcrService:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_version: str | None = None,
        language: str | None = None,
        max_wait_seconds: int | None = None,
        poll_interval_seconds: float | None = None,
        request_timeout_seconds: int | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("MINERU_API_KEY") or os.getenv(
            "MINERU_TOKEN"
        )
        if not self.api_key:
            raise MinerUServiceError("请先在 .env 中配置 MINERU_API_KEY。")

        self.base_url = (
            base_url or os.getenv("MINERU_BASE_URL", "https://mineru.net/api/v4")
        ).rstrip("/")
        self.model_version = model_version or os.getenv("MINERU_MODEL_VERSION", "vlm")
        self.language = language or os.getenv("MINERU_LANGUAGE", "ch")
        self.max_wait_seconds = max_wait_seconds or int(
            os.getenv("MINERU_MAX_WAIT_SECONDS", "300")
        )
        self.poll_interval_seconds = poll_interval_seconds or float(
            os.getenv("MINERU_POLL_INTERVAL_SECONDS", "5")
        )
        self.request_timeout_seconds = request_timeout_seconds or int(
            os.getenv("MINERU_REQUEST_TIMEOUT_SECONDS", "30")
        )

    def parse_file(self, file_path: Path, is_ocr: bool = True) -> str:
        batch_id = self._create_upload_batch(file_path=file_path, is_ocr=is_ocr)
        full_zip_url = self._wait_for_batch_result(batch_id)
        return self._download_markdown_from_zip(full_zip_url)

    def _create_upload_batch(self, file_path: Path, is_ocr: bool) -> str:
        payload = {
            "files": [
                {
                    "name": file_path.name,
                    "data_id": file_path.stem[:128],
                    "is_ocr": is_ocr,
                }
            ],
            "model_version": self.model_version,
            "language": self.language,
            "enable_formula": True,
            "enable_table": True,
        }
        response = self._post_json("/file-urls/batch", payload)
        data = self._payload_data(response)

        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls")
        if not batch_id or not isinstance(file_urls, list) or not file_urls:
            raise MinerUServiceError(f"MinerU 未返回上传地址：{response}")

        self._upload_file(file_path, str(file_urls[0]))
        return str(batch_id)

    def _wait_for_batch_result(self, batch_id: str) -> str:
        deadline = time.monotonic() + self.max_wait_seconds

        while True:
            response = self._get_json(f"/extract-results/batch/{batch_id}")
            data = self._payload_data(response)
            extract_result = data.get("extract_result")
            if isinstance(extract_result, list):
                result = extract_result[0] if extract_result else {}
            elif isinstance(extract_result, dict):
                result = extract_result
            else:
                result = {}

            state = str(result.get("state") or "").lower()
            if state == "done":
                full_zip_url = result.get("full_zip_url")
                if not full_zip_url:
                    raise MinerUServiceError(f"MinerU 解析完成但未返回结果包：{response}")
                return str(full_zip_url)

            if state == "failed":
                raise MinerUServiceError(f"MinerU 解析失败：{result.get('err_msg')}")

            if time.monotonic() >= deadline:
                raise MinerUServiceError(f"MinerU 文档解析超时。batch_id：{batch_id}")

            time.sleep(self.poll_interval_seconds)

    def _download_markdown_from_zip(self, full_zip_url: str) -> str:
        try:
            with urlopen(full_zip_url, timeout=self.request_timeout_seconds) as response:
                zip_bytes = response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise MinerUServiceError(
                f"下载 MinerU 解析结果失败（HTTP {exc.code}）：{body}"
            ) from exc
        except URLError as exc:
            raise MinerUServiceError(f"下载 MinerU 解析结果失败：{exc.reason}") from exc

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "mineru-result.zip"
            zip_path.write_bytes(zip_bytes)
            with zipfile.ZipFile(zip_path) as archive:
                markdown_names = [
                    name
                    for name in archive.namelist()
                    if name.endswith("full.md") or name.lower().endswith(".md")
                ]
                if not markdown_names:
                    raise MinerUServiceError("MinerU 结果包中没有找到 Markdown 文件。")

                with archive.open(markdown_names[0]) as markdown_file:
                    return markdown_file.read().decode("utf-8", errors="replace")

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        return self._request_json(request)

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
        return self._request_json(request)

    def _request_json(self, request: Request) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=self.request_timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise MinerUServiceError(
                f"MinerU 请求失败（HTTP {exc.code}）：{body}"
            ) from exc
        except URLError as exc:
            raise MinerUServiceError(f"无法连接 MinerU 服务：{exc.reason}") from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MinerUServiceError(f"MinerU 返回了非 JSON 内容：{body}") from exc

        if not isinstance(data, dict):
            raise MinerUServiceError(f"MinerU 返回格式不正确：{data}")

        code = data.get("code")
        if code not in (None, 0, "0"):
            raise MinerUServiceError(data.get("msg") or f"MinerU 请求失败：{data}")

        return data

    def _upload_file(self, file_path: Path, upload_url: str) -> None:
        request = Request(
            upload_url,
            data=file_path.read_bytes(),
            method="PUT",
        )
        try:
            with urlopen(request, timeout=self.request_timeout_seconds) as response:
                if response.status not in (200, 201, 204):
                    raise MinerUServiceError(
                        f"上传文件到 MinerU 失败，HTTP 状态码：{response.status}"
                    )
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise MinerUServiceError(
                f"上传文件到 MinerU 失败（HTTP {exc.code}）：{body}"
            ) from exc
        except URLError as exc:
            raise MinerUServiceError(f"上传文件到 MinerU 失败：{exc.reason}") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _payload_data(self, response: dict[str, Any]) -> dict[str, Any]:
        data = response.get("data")
        return data if isinstance(data, dict) else response
