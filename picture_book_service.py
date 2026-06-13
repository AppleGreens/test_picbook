import os
import uuid
from pathlib import Path

from document_service import DocumentParseError, DocumentParser
from image_service import ImageServiceError, NanoBananaImageService
from mineru_service import MinerUOcrService, MinerUServiceError
from models import DocumentContent, PictureBookPage, PictureBookResult
from outline_service import OutlineGenerationError, PictureBookOutlineService
from pdf_export_service import PdfExportError, PictureBookPdfExporter


class PictureBookError(RuntimeError):
    """Raised when the picture book generation pipeline fails."""


class PictureBookService:
    def __init__(
        self,
        output_dir: Path,
        upload_dir: Path,
        document_parser: DocumentParser | None = None,
        outline_service: PictureBookOutlineService | None = None,
        image_service: NanoBananaImageService | None = None,
        pdf_exporter: PictureBookPdfExporter | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.upload_dir = upload_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        self.document_parser = document_parser or DocumentParser(
            mineru_service=self._build_optional_mineru_service()
        )
        self.outline_service = outline_service or PictureBookOutlineService()
        self.image_service = image_service or NanoBananaImageService()
        self.pdf_exporter = pdf_exporter or PictureBookPdfExporter(self.output_dir)

    def create_from_text(
        self,
        text: str,
        aspect_ratio: str = "16:9",
        image_size: str = "2k",
        page_count: int = 6,
        reference_image_urls: list[str] | None = None,
    ) -> PictureBookResult:
        document = DocumentContent(text=text, source_name="text")
        return self._create(
            document=document,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            page_count=page_count,
            reference_image_urls=reference_image_urls,
        )

    def create_from_file(
        self,
        file_path: Path,
        aspect_ratio: str = "16:9",
        image_size: str = "2k",
        page_count: int = 6,
        reference_image_urls: list[str] | None = None,
    ) -> PictureBookResult:
        try:
            document = self.document_parser.parse(file_path)
        except DocumentParseError as exc:
            raise PictureBookError(str(exc)) from exc

        return self._create(
            document=document,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            page_count=page_count,
            reference_image_urls=reference_image_urls,
        )

    def _create(
        self,
        document: DocumentContent,
        aspect_ratio: str,
        image_size: str,
        page_count: int,
        reference_image_urls: list[str] | None,
    ) -> PictureBookResult:
        job_id = uuid.uuid4().hex

        try:
            title, pages = self.outline_service.generate_outline(
                document.text,
                page_count=page_count,
            )
            pages_with_images = self._generate_page_images(
                job_id=job_id,
                pages=pages,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                reference_image_urls=reference_image_urls,
            )
            pdf_path = self.pdf_exporter.export(
                title=title,
                pages=pages_with_images,
                output_name=f"{job_id}.pdf",
            )
        except (OutlineGenerationError, ImageServiceError, PdfExportError) as exc:
            raise PictureBookError(str(exc)) from exc

        return PictureBookResult(
            job_id=job_id,
            title=title,
            source_name=document.source_name,
            pages=pages_with_images,
            pdf_path=pdf_path,
            parsed_text=document.text,
        )

    def _generate_page_images(
        self,
        job_id: str,
        pages: list[PictureBookPage],
        aspect_ratio: str,
        image_size: str,
        reference_image_urls: list[str] | None,
    ) -> list[PictureBookPage]:
        generated_pages: list[PictureBookPage] = []
        references = [url for url in reference_image_urls or [] if url]
        for page in pages:
            prompt = page.image_prompt
            if references:
                prompt = (
                    f"{prompt}\n\nUse the uploaded reference photo(s) as character "
                    "identity references. Integrate the real person from the photo "
                    "into the cartoon picture-book scene while keeping the scene "
                    "warm, child-friendly, and story-driven."
                )
            image_result = self.image_service.generate_image(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                reference_image_urls=references,
            )
            image_path = self.images_dir / f"{job_id}_page_{page.page_number}.png"
            image_path.write_bytes(image_result.image_bytes)
            generated_pages.append(
                PictureBookPage(
                    page_number=page.page_number,
                    title=page.title,
                    narration=page.narration,
                    image_prompt=page.image_prompt,
                    narrative_goal=page.narrative_goal,
                    key_content=page.key_content,
                    visual=page.visual,
                    layout=page.layout,
                    image_path=image_path,
                )
            )
        return generated_pages

    def _build_optional_mineru_service(self) -> MinerUOcrService | None:
        if not (os.getenv("MINERU_API_KEY") or os.getenv("MINERU_TOKEN")):
            return None

        try:
            return MinerUOcrService()
        except MinerUServiceError:
            return None
