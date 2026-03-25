"""Configuration for the aide-memoire pipeline."""

from dataclasses import dataclass, field
from pathlib import Path

from aide_memoire.models import PaperFormat


@dataclass
class Config:
    input_files: list[Path] = field(default_factory=list)
    output_dir: Path = Path("output")
    paper_format: PaperFormat = PaperFormat.LETTER_3COL
    title: str = "Exam Review Sheet"
    author: str = ""
    intel_path: Path | None = None
    model: str = "claude-sonnet-4-20250514"
    max_boxes: int | None = None
    expected_pages: int = 2
    no_compile: bool = False
    no_verify: bool = False
    max_retries: int = 3
