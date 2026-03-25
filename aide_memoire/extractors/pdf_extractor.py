"""PDF content extractor using PyMuPDF."""

from pathlib import Path

import fitz

from aide_memoire.extractors.base import BaseExtractor
from aide_memoire.models import ContentBlock, ContentType, ExtractedDocument


class PdfExtractor(BaseExtractor):
    def extract(self, file_path: Path, output_dir: Path | None = None) -> ExtractedDocument:
        pdf = fitz.open(str(file_path))
        doc = ExtractedDocument(source_path=file_path, title=file_path.stem)

        image_dir = None
        if output_dir:
            image_dir = output_dir / "images"
            image_dir.mkdir(parents=True, exist_ok=True)

        for page_idx in range(len(pdf)):
            page = pdf[page_idx]
            location = f"Page {page_idx + 1}"

            # Extract text
            text = page.get_text("text")
            if text.strip():
                doc.blocks.append(ContentBlock(
                    content_type=ContentType.TEXT,
                    text=text.strip(),
                    source_file=file_path.name,
                    source_location=location,
                ))

            # Extract images
            if image_dir:
                for img_idx, img_info in enumerate(page.get_images(full=True)):
                    xref = img_info[0]
                    try:
                        base_image = pdf.extract_image(xref)
                        ext = base_image["ext"]
                        image_bytes = base_image["image"]
                        filename = f"page{page_idx + 1}_img{img_idx}.{ext}"
                        image_path = image_dir / filename
                        image_path.write_bytes(image_bytes)
                        doc.blocks.append(ContentBlock(
                            content_type=ContentType.IMAGE,
                            text=str(image_path),
                            source_file=file_path.name,
                            source_location=location,
                        ))
                    except Exception:
                        continue

        pdf.close()
        return doc
