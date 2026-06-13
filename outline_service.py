import re
from textwrap import shorten

from models import PictureBookPage


class OutlineGenerationError(RuntimeError):
    """Raised when source text cannot be converted into a picture-book outline."""


class PictureBookOutlineService:
    def __init__(self, default_page_count: int = 6) -> None:
        self.default_page_count = default_page_count

    def generate_outline(
        self,
        source_text: str,
        page_count: int | None = None,
    ) -> tuple[str, list[PictureBookPage]]:
        cleaned_text = self._clean_text(source_text)
        if not cleaned_text:
            raise OutlineGenerationError("没有可用于生成绘本大纲的文字内容。")

        requested_page_count = page_count or self.default_page_count
        page_total = max(1, min(requested_page_count, 12))
        chunks = self._split_into_chunks(cleaned_text, page_total)
        title = self._make_title(cleaned_text)

        pages: list[PictureBookPage] = []
        for index, chunk in enumerate(chunks, start=1):
            narration = self._make_child_friendly_narration(chunk, index, len(chunks))
            page_title = f"第 {index} 页"
            image_prompt = self._make_image_prompt(title, narration)
            pages.append(
                PictureBookPage(
                    page_number=index,
                    title=page_title,
                    narration=narration,
                    image_prompt=image_prompt,
                )
            )

        return title, pages

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"#+\s*", "", text)
        text = re.sub(r"[*_`>-]+", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_into_chunks(self, text: str, page_count: int) -> list[str]:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[。！？!?\.])\s*", text)
            if sentence.strip()
        ]
        if not sentences:
            sentences = [text]

        chunk_count = min(page_count, len(sentences)) or 1
        chunk_size = max(1, (len(sentences) + chunk_count - 1) // chunk_count)
        return [
            " ".join(sentences[index : index + chunk_size])
            for index in range(0, len(sentences), chunk_size)
        ][:chunk_count]

    def _make_title(self, text: str) -> str:
        first_sentence = re.split(r"[。！？!?\.]", text, maxsplit=1)[0].strip()
        if not first_sentence:
            return "我的儿童绘本"
        return shorten(first_sentence, width=24, placeholder="...")

    def _make_child_friendly_narration(
        self,
        chunk: str,
        page_number: int,
        page_count: int,
    ) -> str:
        short_chunk = shorten(chunk, width=90, placeholder="...")
        if page_number == 1:
            return f"故事开始了。{short_chunk}"
        if page_number == page_count:
            return f"最后，大家明白了一个温暖的小道理：{short_chunk}"
        return f"接着，新的发现出现了。{short_chunk}"

    def _make_image_prompt(self, title: str, narration: str) -> str:
        return (
            f"Create a children's picture book illustration for the story '{title}'. "
            f"Scene: {narration}. Warm soft colors, gentle lighting, whimsical, "
            "hand-drawn texture, child-friendly, no text, no watermark."
        )
