"""Overflow and layout verification for compiled PDFs."""

from dataclasses import dataclass, field
from pathlib import Path

import fitz


@dataclass
class VerificationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


class OverflowVerifier:
    def verify(self, pdf_path: Path, expected_pages: int = 1) -> VerificationResult:
        """Verify a compiled PDF for overflow and layout issues."""
        doc = fitz.open(str(pdf_path))
        result = VerificationResult()

        # Check 1: Page count
        if len(doc) > expected_pages:
            result.errors.append(
                f"Expected {expected_pages} page(s), got {len(doc)}. Content overflowed."
            )

        # Check 2: Text beyond page boundaries and overlap detection
        for page_idx in range(min(len(doc), expected_pages)):
            page = doc[page_idx]
            page_rect = page.rect
            page_height = page_rect.height
            page_width = page_rect.width

            text_blocks = page.get_text("blocks")
            # blocks: list of (x0, y0, x1, y1, text, block_no, block_type)

            for block in text_blocks:
                x0, y0, x1, y1 = block[:4]

                # Check if text extends past bottom of page
                if y1 > page_height - 2:
                    result.errors.append(
                        f"Page {page_idx + 1}: Text extends past page bottom "
                        f"(y={y1:.1f}, page height={page_height:.1f})"
                    )

                # Check if text extends past right edge
                if x1 > page_width - 2:
                    result.warnings.append(
                        f"Page {page_idx + 1}: Text near right edge "
                        f"(x={x1:.1f}, page width={page_width:.1f})"
                    )

            # Check for vertical overlap between blocks in the same column
            if text_blocks:
                # Group blocks by approximate column (x-position)
                columns: dict[int, list] = {}
                for block in text_blocks:
                    col_key = int(block[0] / 100)  # Group by 100pt-wide columns
                    columns.setdefault(col_key, []).append(block)

                for col_key, col_blocks in columns.items():
                    # Sort by y-position within each column
                    sorted_blocks = sorted(col_blocks, key=lambda b: b[1])
                    for i in range(len(sorted_blocks) - 1):
                        curr_bottom = sorted_blocks[i][3]
                        next_top = sorted_blocks[i + 1][1]
                        overlap = curr_bottom - next_top
                        if overlap > 5:  # More than 5pt overlap
                            result.warnings.append(
                                f"Page {page_idx + 1}: Possible box overlap "
                                f"({overlap:.1f}pt) in column ~{col_key}"
                            )

        doc.close()
        return result
