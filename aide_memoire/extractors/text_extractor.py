"""Plain text file extractor."""

from pathlib import Path

from aide_memoire.extractors.base import BaseExtractor
from aide_memoire.models import ContentBlock, ContentType, ExtractedDocument


class TextExtractor(BaseExtractor):
    def extract(self, file_path: Path, output_dir: Path | None = None) -> ExtractedDocument:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        doc = ExtractedDocument(source_path=file_path, title=file_path.stem)

        if text.strip():
            doc.blocks.append(ContentBlock(
                content_type=ContentType.TEXT,
                text=text.strip(),
                source_file=file_path.name,
                source_location="Full file",
            ))

        return doc
