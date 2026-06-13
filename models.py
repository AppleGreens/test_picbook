from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DocumentContent:
    text: str
    source_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PictureBookPage:
    page_number: int
    title: str
    narration: str
    image_prompt: str
    image_path: Path | None = None


@dataclass(frozen=True)
class PictureBookResult:
    job_id: str
    title: str
    source_name: str
    pages: list[PictureBookPage]
    pdf_path: Path
    parsed_text: str
