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
    narrative_goal: str
    key_content: str
    visual: str
    layout: str
    image_path: Path | None = None


@dataclass(frozen=True)
class CharacterProfile:
    name: str
    description: str
    style: str
    reference_prompt: str
    reference_image_path: Path | None = None
    reference_image_url: str | None = None


@dataclass(frozen=True)
class PictureBookResult:
    job_id: str
    title: str
    source_name: str
    character_profile: CharacterProfile | None
    pages: list[PictureBookPage]
    pdf_path: Path
    parsed_text: str
