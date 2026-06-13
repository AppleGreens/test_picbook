import re
from pathlib import Path

from docx import Document

from mineru_service import MinerUOcrService, MinerUServiceError
from models import DocumentContent


class DocumentParseError(RuntimeError):
    """Raised when an uploaded document cannot be parsed."""


class DocumentParser:
    SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}

    def __init__(self, mineru_service: MinerUOcrService | None = None) -> None:
        self.mineru_service = mineru_service

    def parse(self, file_path: Path) -> DocumentContent:
        extension = file_path.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise DocumentParseError("仅支持 PDF、Word（.doc/.docx）和 TXT 文件。")

        if extension == ".txt":
            text = self._read_txt(file_path)
            parser = "local_txt"
        elif extension == ".docx" and self.mineru_service is None:
            text = self._read_docx(file_path)
            parser = "local_docx"
        else:
            text = self._parse_with_mineru(file_path)
            parser = "mineru"

        cleaned_text = self._clean_text(text)
        if not cleaned_text:
            raise DocumentParseError("文档解析完成，但没有提取到有效文字内容。")

        return DocumentContent(
            text=cleaned_text,
            source_name=file_path.name,
            metadata={"parser": parser, "extension": extension},
        )

    def _parse_with_mineru(self, file_path: Path) -> str:
        if self.mineru_service is None:
            raise DocumentParseError(
                "PDF、.doc 文件和带图片的 Word 解析需要配置 MINERU_API_KEY。"
            )

        try:
            return self.mineru_service.parse_file(file_path=file_path, is_ocr=True)
        except MinerUServiceError as exc:
            raise DocumentParseError(str(exc)) from exc

    def _read_txt(self, file_path: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise DocumentParseError("TXT 文件编码无法识别，请使用 UTF-8 编码。")

    def _read_docx(self, file_path: Path) -> str:
        document = Document(file_path)
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
        return "\n".join(paragraph for paragraph in paragraphs if paragraph)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"!\[[^\]]*]\([^)]*\)", "", text)
        text = re.sub(r"\[[^\]]*]\([^)]*\)", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
