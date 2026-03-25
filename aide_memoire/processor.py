"""Claude API content processor: extracts → condenses → LaTeX boxes."""

import re

import anthropic

from aide_memoire.models import Box, ContentBlock, ExtractedDocument, PaperFormat

# Format-specific constraints for the prompt
FORMAT_CONSTRAINTS = {
    PaperFormat.LETTER_3COL: {
        "description": "8.5x11 inch landscape paper, 3 columns",
        "minipage_width": "0.3\\textwidth",
        "max_boxes": 12,
        "density_note": (
            "You have a FULL page with 3 columns to fill. Generate 8-12 boxes. "
            "Each box should contain 15-30 lines of dense content with formulas, "
            "tables, and definitions. The content MUST fill all 3 columns — "
            "approximately 300+ lines total across all boxes."
        ),
    },
    PaperFormat.LETTER_4COL: {
        "description": "8.5x11 inch landscape paper, 4 columns",
        "minipage_width": "0.2\\textwidth",
        "max_boxes": 16,
        "density_note": (
            "You have a FULL page with 4 columns to fill. Generate 10-16 boxes. "
            "Each box should contain 10-25 lines of dense content. "
            "The content MUST fill all 4 columns."
        ),
    },
    PaperFormat.NOTECARD: {
        "description": "4x6 inch landscape notecard, 2 columns",
        "minipage_width": "0.96\\columnwidth",
        "max_boxes": 6,
        "density_note": (
            "You have a small 4x6 inch notecard with 2 columns. "
            "Generate 4-6 boxes. Be extremely concise."
        ),
    },
}

SYSTEM_PROMPT = """\
You are an expert at creating dense, high-quality exam reference cards (cheat sheets) in LaTeX.

Your job: take extracted course material and produce the INNER CONTENT of LaTeX boxes for a cheat sheet.
You do NOT produce the full LaTeX document — only the content that goes inside each box.

CRITICAL FORMATTING RULES:
- Content will be wrapped in {\\tiny ...}, so everything is already tiny font.
- Use \\textbf{} for bold, \\textit{} for italic.
- Use \\ctitle{Subtitle} for sub-headings within a box (pre-defined command that creates a centered underlined bold heading).
- For math: use $...$ inline or \\begin{align*}...\\end{align*} for display equations.
- For tables: use \\setlength\\tabcolsep{2pt} then \\begin{tabular}{cols}...\\end{tabular}.
- For lists: use \\begin{itemize}[leftmargin=*,topsep=0pt,itemsep=0pt,parsep=0pt] ... \\end{itemize}
- For code: use \\begin{lstlisting}[language={...},basicstyle={\\tiny\\ttfamily},tabsize=4] ... \\end{lstlisting}
- Use \\\\ for line breaks within flowing text.
- Do NOT use \\vspace with negative values — these cause text overlap.
- Do NOT use \\begin{spacing} — the template handles spacing.

CONTENT VOLUME — THIS IS CRITICAL:
- For a 3-column letter page: generate SUBSTANTIAL content. Each box should have 15-30 lines of content.
- The boxes need to fill ALL 3 columns of the page. If you generate too little, the page will be mostly empty.
- Include ALL relevant formulas, definitions, procedures, and worked examples from the source material.
- Include comparison tables, step-by-step procedures, and edge cases.
- It's better to include slightly too much than too little — overflow will be detected and fixed automatically.
- Aim to PACK every box with as much useful information as possible.
- Use tabular environments for structured comparisons — they fill space efficiently and are very readable.

CONTENT DENSITY STYLE:
- Prioritize: formulas > definitions > procedures > key examples > explanations.
- Use symbols and shorthand over words when the meaning is clear.
- For hypothesis tests, use the compact tabular format:
  \\setlength\\tabcolsep{2pt}
  \\begin{tabular}{p{0.1\\textwidth}p{0.75\\textwidth}}
    {\\bf $H_0$}: & ... \\\\
    {\\bf $H_A$}: & ...
  \\end{tabular}

LaTeX SAFETY:
- & is ONLY allowed inside tabular/align environments. Everywhere else use \\&.
- In \\ctitle{} arguments: escape & as \\& (ctitle is not a tabular context).
- Do NOT use \\begin{document}, \\documentclass, or any preamble commands.
- Do NOT wrap content in {\\tiny ...} or \\begin{spacing} — handled by template.
- Do NOT use \\section, \\subsection, or other sectioning commands.

OUTPUT FORMAT:
For each box, output exactly:
%%% BOX: <title> %%%
<latex content for inside the box>
%%% END %%%

Output ONLY boxes in this format. No other text, commentary, or explanation.\
"""


def _build_user_prompt(
    documents: list[ExtractedDocument],
    intel_hints: list[str] | None,
    paper_format: PaperFormat,
    max_boxes: int | None,
) -> str:
    constraints = FORMAT_CONSTRAINTS[paper_format]
    effective_max = max_boxes or constraints["max_boxes"]

    parts = [
        f"TARGET FORMAT: {constraints['description']}",
        f"CONSTRAINT: {constraints['density_note']}",
        f"Maximum boxes: {effective_max}",
        "",
    ]

    if intel_hints:
        parts.append("INTEL HINTS (prioritize/deprioritize topics accordingly):")
        for hint in intel_hints:
            parts.append(f"  - {hint}")
        parts.append("")

    parts.append("EXTRACTED COURSE MATERIAL:")
    parts.append("=" * 60)

    for doc in documents:
        parts.append(f"\n--- SOURCE: {doc.title} ({doc.source_path.name}) ---\n")
        for block in doc.blocks:
            if block.content_type.value == "image":
                continue  # Skip image paths, they can't go in the prompt
            prefix = f"[{block.source_location}]"
            parts.append(f"{prefix} {block.text}")
        parts.append("")

    parts.append("=" * 60)
    parts.append(
        f"\nNow generate {effective_max} or fewer boxes of dense LaTeX cheat sheet "
        f"content covering the most important material above. Group related topics "
        f"into the same box. Every box must have a clear, descriptive title."
    )

    return "\n".join(parts)


def _parse_boxes(response_text: str) -> list[Box]:
    """Parse Claude's response into Box objects."""
    boxes = []
    pattern = r"%%% BOX:\s*(.+?)\s*%%%(.*?)%%% END %%%"
    matches = re.findall(pattern, response_text, re.DOTALL)
    for title, content in matches:
        latex_content = content.strip()
        if latex_content:
            # Store raw title — escaping happens at render time via latex_escape filter
            clean_title = title.strip()
            # Strip any escaping Claude may have added — the filter will re-escape
            clean_title = clean_title.replace(r"\&", "&").replace(r"\%", "%")
            clean_title = clean_title.replace(r"\#", "#").replace(r"\_", "_")
            boxes.append(Box(title=clean_title, latex_content=latex_content))
    return boxes


class ContentProcessor:
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()
        self.model = model

    def process(
        self,
        documents: list[ExtractedDocument],
        intel_hints: list[str] | None = None,
        paper_format: PaperFormat = PaperFormat.LETTER_3COL,
        max_boxes: int | None = None,
    ) -> list[Box]:
        """Process extracted documents into cheat sheet boxes."""
        user_prompt = _build_user_prompt(documents, intel_hints, paper_format, max_boxes)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = response.content[0].text
        boxes = _parse_boxes(response_text)

        if not boxes:
            raise ValueError(
                "Failed to parse any boxes from Claude's response. "
                f"Response started with: {response_text[:200]}"
            )

        return boxes

    def condense(
        self,
        boxes: list[Box],
        overflow_errors: list[str],
        paper_format: PaperFormat = PaperFormat.LETTER_3COL,
    ) -> list[Box]:
        """Ask Claude to make boxes shorter to fix overflow."""
        current_boxes = "\n\n".join(
            f"%%% BOX: {b.title} %%%\n{b.latex_content}\n%%% END %%%" for b in boxes
        )

        prompt = (
            f"The following cheat sheet boxes caused overflow on "
            f"{FORMAT_CONSTRAINTS[paper_format]['description']}.\n\n"
            f"OVERFLOW ERRORS:\n" + "\n".join(f"- {e}" for e in overflow_errors) + "\n\n"
            f"Reduce total content by approximately 20%. Strategies:\n"
            f"- Remove the least important examples\n"
            f"- Shorten verbose explanations\n"
            f"- Combine small related boxes\n"
            f"- Use more abbreviations and symbols\n"
            f"- Keep ALL formulas and key definitions\n\n"
            f"CURRENT BOXES:\n{current_boxes}\n\n"
            f"Output the condensed boxes in the same %%% BOX: title %%% ... %%% END %%% format."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        new_boxes = _parse_boxes(response.content[0].text)
        return new_boxes if new_boxes else boxes
