"""Abstract base extractor and factory."""

from abc import ABC, abstractmethod
from pathlib import Path

from aide_memoire.models import ExtractedDocument


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path, output_dir: Path | None = None) -> ExtractedDocument:
        """Extract all content from the given file."""
        ...

    @staticmethod
    def for_file(file_path: Path) -> "BaseExtractor":
        """Return the right extractor for a file extension."""
        suffix = file_path.suffix.lower()
        if suffix == ".pptx":
            from aide_memoire.extractors.pptx_extractor import PptxExtractor
            return PptxExtractor()
        elif suffix == ".pdf":
            from aide_memoire.extractors.pdf_extractor import PdfExtractor
            return PdfExtractor()
        elif suffix == ".docx":
            from aide_memoire.extractors.docx_extractor import DocxExtractor
            return DocxExtractor()
        elif suffix == ".txt":
            from aide_memoire.extractors.text_extractor import TextExtractor
            return TextExtractor()
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
