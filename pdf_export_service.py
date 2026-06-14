from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

from models import PictureBookPage


class PdfExportError(RuntimeError):
    """Raised when a picture book cannot be exported as PDF."""


class PictureBookPdfExporter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    def export(
        self,
        title: str,
        pages: list[PictureBookPage],
        output_name: str,
    ) -> Path:
        if not pages:
            raise PdfExportError("没有可导出的绘本页面。")

        output_path = self.output_dir / output_name
        pdf_canvas = canvas.Canvas(str(output_path), pagesize=landscape(A4))
        page_width, page_height = landscape(A4)

        self._draw_cover(pdf_canvas, title, page_width, page_height)
        for page in pages:
            self._draw_picture_page(pdf_canvas, page, page_width, page_height)

        pdf_canvas.save()
        return output_path

    def _draw_cover(
        self,
        pdf_canvas: canvas.Canvas,
        title: str,
        page_width: float,
        page_height: float,
    ) -> None:
        pdf_canvas.setFillColor(colors.HexColor("#FFF7E6"))
        pdf_canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        pdf_canvas.setFillColor(colors.HexColor("#5C4033"))
        pdf_canvas.setFont("STSong-Light", 32)
        pdf_canvas.drawCentredString(page_width / 2, page_height / 2 + 20 * mm, title)
        pdf_canvas.setFont("STSong-Light", 16)
        pdf_canvas.drawCentredString(
            page_width / 2,
            page_height / 2 - 5 * mm,
            "AI 自动生成儿童绘本",
        )
        pdf_canvas.showPage()

    def _draw_picture_page(
        self,
        pdf_canvas: canvas.Canvas,
        page: PictureBookPage,
        page_width: float,
        page_height: float,
    ) -> None:
        pdf_canvas.setFillColor(colors.white)
        pdf_canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)

        margin = 18 * mm
        image_box_height = page_height * 0.68
        text_top = page_height - image_box_height - margin

        if page.image_path and page.image_path.exists():
            self._draw_image(
                pdf_canvas=pdf_canvas,
                image_path=page.image_path,
                x=margin,
                y=page_height - image_box_height - margin,
                max_width=page_width - margin * 2,
                max_height=image_box_height,
            )
        else:
            pdf_canvas.setFillColor(colors.HexColor("#FFF0C9"))
            pdf_canvas.roundRect(
                margin,
                page_height - image_box_height - margin,
                page_width - margin * 2,
                image_box_height,
                8 * mm,
                fill=1,
                stroke=0,
            )

        pdf_canvas.setFillColor(colors.HexColor("#5C4033"))
        pdf_canvas.setFont("STSong-Light", 15)
        pdf_canvas.drawString(margin, text_top - 5 * mm, page.title)

        narration_style = ParagraphStyle(
            "PictureBookNarration",
            fontName="STSong-Light",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#3D2B1F"),
        )
        page_plan = (
            f"<b>// NARRATIVE GOAL</b> {page.narrative_goal}<br/>"
            f"<b>// KEY CONTENT</b> {page.key_content}<br/>"
            f"<b>// VISUAL</b> {page.visual}<br/>"
            f"<b>// LAYOUT</b> {page.layout}<br/><br/>"
            f"{page.narration}"
        )
        paragraph = Paragraph(page_plan, narration_style)
        paragraph.wrapOn(pdf_canvas, page_width - margin * 2, 48 * mm)
        paragraph.drawOn(pdf_canvas, margin, margin - 2 * mm)

        pdf_canvas.showPage()

    def _draw_image(
        self,
        pdf_canvas: canvas.Canvas,
        image_path: Path,
        x: float,
        y: float,
        max_width: float,
        max_height: float,
    ) -> None:
        try:
            with Image.open(image_path) as image:
                image.thumbnail((int(max_width), int(max_height)))
                buffer = BytesIO()
                image.convert("RGB").save(buffer, format="PNG")
                buffer.seek(0)
                draw_x = x + (max_width - image.width) / 2
                draw_y = y + (max_height - image.height) / 2
                pdf_canvas.drawInlineImage(
                    Image.open(buffer),
                    draw_x,
                    draw_y,
                    width=image.width,
                    height=image.height,
                )
        except OSError as exc:
            raise PdfExportError(f"无法读取绘本图片：{image_path}") from exc
