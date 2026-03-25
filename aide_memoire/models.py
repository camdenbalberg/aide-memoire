"""Data models for the aide-memoire pipeline."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ContentType(Enum):
    TEXT = "text"
    MATH = "math"
    TABLE = "table"
    CODE = "code"
    IMAGE = "image"
    LIST = "list"


class PaperFormat(Enum):
    LETTER_3COL = "letter_3col"
    LETTER_4COL = "letter_4col"
    NOTECARD = "notecard"


@dataclass
class ContentBlock:
    """A single piece of extracted content."""
    content_type: ContentType
    text: str
    source_file: str
    source_location: str  # e.g. "Slide 5" or "Page 12"
    importance: float = 0.5


@dataclass
class ExtractedDocument:
    """All content extracted from one input file."""
    source_path: Path
    title: str
    blocks: list[ContentBlock] = field(default_factory=list)


@dataclass
class Box:
    """A single box on the cheat sheet."""
    title: str
    latex_content: str


@dataclass
class Sheet:
    """A complete cheat sheet page."""
    title: str
    author: str
    paper_format: PaperFormat
    boxes: list[Box] = field(default_factory=list)
