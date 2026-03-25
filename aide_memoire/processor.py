"""Claude API content processor: extracts → condenses → LaTeX boxes."""

import re

import anthropic

from aide_memoire.models import Box, ContentBlock, ExtractedDocument, PaperFormat

# Format-specific constraints for the prompt
FORMAT_CONSTRAINTS = {
    PaperFormat.LETTER_3COL: {
        "description": "8.5x11 inch landscape paper, 3 columns, 2 PAGES (front and back)",
        "max_boxes": 20,
        "density_note": (
            "You have TWO FULL 8.5x11 landscape pages (front and back of one sheet) with 3 wide columns each. "
            "That is 6 total columns of space. Generate 14-20 boxes to fill both pages. "
            "Each box should be PACKED with content — 25-45 lines each. "
            "Total content should be 700+ lines across all boxes. "
            "Write VERBOSE definitions that span the full width of the line. "
            "Include plain English explanations, step-by-step procedures, and worked examples with numbers. "
            "Do NOT use fragments or shorthand — write full sentences so a student can "
            "understand the material just from reading the cheat sheet. "
            "Include common mistakes, edge cases, and tips."
        ),
    },
    PaperFormat.LETTER_4COL: {
        "description": "8.5x11 inch landscape paper, 4 columns, 2 PAGES (front and back)",
        "max_boxes": 24,
        "density_note": (
            "You have TWO FULL 8.5x11 landscape pages (front and back) with 4 columns each. "
            "That is 8 total columns of space. Generate 16-24 boxes. "
            "Each box should be densely packed with content. "
            "Write clear definitions, include examples, and explain concepts thoroughly."
        ),
    },
    PaperFormat.NOTECARD: {
        "description": "4x6 inch landscape notecard, 2 columns",
        "max_boxes": 6,
        "density_note": (
            "You have a small 4x6 inch notecard with 2 columns. "
            "Generate 4-6 boxes. Be extremely concise."
        ),
    },
}

SYSTEM_PROMPT = """\
You are an expert at creating comprehensive, self-contained exam reference cards (cheat sheets) in LaTeX.

Your job: take extracted course material and produce the INNER CONTENT of LaTeX boxes for a cheat sheet.
You do NOT produce the full LaTeX document — only the content that goes inside each box.

CONTENT PHILOSOPHY — READ THIS CAREFULLY:
- The cheat sheet must be so thorough that ANY student can pick it up and do well on the exam.
- Write VERBOSE, complete definitions — not shorthand fragments. Each definition should be a full
  sentence that explains the concept clearly. For example, instead of "P(A): Number between 0 and 1",
  write "The probability of an event A, written P(A), is a number between 0 and 1 that measures
  how likely event A is to occur."
- Include plain English explanations of WHY formulas work and WHEN to use them.
- Include WORKED EXAMPLES with actual numbers for every major formula or procedure. Show the setup,
  substitution, and final answer. Examples are critical — they show students how to actually apply concepts.
- Every line of text should extend close to the full width of the box. If a definition or explanation
  ends far before the right edge, you are wasting space — expand it with more detail or context.
- Include step-by-step procedures: "Step 1: ... Step 2: ..." for multi-step processes like hypothesis
  tests, probability calculations, etc.
- Include common mistakes, edge cases, and "watch out for" notes where relevant.
- Use comparison tables to contrast related concepts side-by-side.

FORMATTING RULES:
- Content will be wrapped in {\\scriptsize ...}, so everything is already small font.
- Use \\textbf{} for bold terms being defined, \\textit{} for emphasis.
- Use \\ctitle{Subtitle} for sub-headings within a box (creates a centered underlined bold heading).
- For math: STRONGLY prefer inline $...$ for single equations. Write the formula inline with its
  explanation, e.g. "The expected value is $E(X) = \\sum x \\cdot P(X=x)$, which represents the long-run average."
  Only use \\begin{align*}...\\end{align*} when you have MULTIPLE related equations that must be aligned.
  Display math environments add large vertical gaps that waste space.
- For tables: use \\setlength\\tabcolsep{2pt} then \\begin{tabular}{cols}...\\end{tabular}.
  Use p{<width>} column types for text that should wrap to fill the column width.
- For lists: use \\begin{itemize}[leftmargin=*,topsep=0pt,itemsep=0pt,parsep=0pt] ... \\end{itemize}
- Use \\\\ for line breaks within flowing text.
- Do NOT use \\vspace with negative values — these cause text overlap.
- Do NOT use \\begin{spacing} — the template handles spacing.

FILLING SPACE — CRITICAL:
- Each box should have 25-45 lines of dense content.
- Write definitions as full sentences or short paragraphs, NOT as single-word fragments.
- After a formula, add 1-2 sentences explaining what each variable means and when to use the formula.
- After stating a rule, give a concrete numeric example demonstrating it.
- Text lines should use the full width available. Avoid short fragments that leave the right half empty.
- Tabular environments should use p{} columns that sum to roughly the full minipage width so text wraps
  and fills the space. Example: \\begin{tabular}{p{0.35\\columnwidth}p{0.6\\columnwidth}}.

LaTeX SAFETY:
- & is ONLY allowed inside tabular/align environments. Everywhere else use \\&.
- In \\ctitle{} arguments: escape & as \\& (ctitle is not a tabular context).
- Do NOT use \\begin{document}, \\documentclass, or any preamble commands.
- Do NOT wrap content in {\\tiny ...} or \\begin{spacing} — handled by template.
- Do NOT use \\section, \\subsection, or other sectioning commands.
- Do NOT use $$ ... $$ for display math — use $...$ inline or \\begin{align*} ... \\end{align*}.

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
        f"\nNow generate {effective_max} or fewer boxes of comprehensive LaTeX cheat sheet "
        f"content covering the most important material above. Group related topics "
        f"into the same box. Every box must have a clear, descriptive title.\n\n"
        f"REMEMBER: Write VERBOSE definitions (full sentences, not fragments). Include WORKED "
        f"EXAMPLES with numbers for every major concept. Add plain English explanations of when "
        f"and why to use each formula. Every text line should use the full width of the box — "
        f"do not leave half-empty lines. A student with no prior knowledge should be able to "
        f"read this sheet and understand how to solve exam problems."
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

    def _stream_response(self, system: str, user_prompt: str) -> str:
        """Stream a response from Claude and return the full text."""
        collected = []
        with self.client.messages.stream(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                collected.append(text)
        return "".join(collected)

    def process(
        self,
        documents: list[ExtractedDocument],
        intel_hints: list[str] | None = None,
        paper_format: PaperFormat = PaperFormat.LETTER_3COL,
        max_boxes: int | None = None,
    ) -> list[Box]:
        """Process extracted documents into cheat sheet boxes."""
        user_prompt = _build_user_prompt(documents, intel_hints, paper_format, max_boxes)

        response_text = self._stream_response(SYSTEM_PROMPT, user_prompt)
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
        actual_pages: int = 0,
        expected_pages: int = 1,
    ) -> list[Box]:
        """Ask Claude to make boxes shorter to fix overflow."""
        current_boxes = "\n\n".join(
            f"%%% BOX: {b.title} %%%\n{b.latex_content}\n%%% END %%%" for b in boxes
        )

        # Calculate the reduction needed
        if actual_pages > 0 and expected_pages > 0:
            ratio = expected_pages / actual_pages
            reduction_pct = int((1 - ratio) * 100)
            # Aim for slightly less reduction to avoid under-filling
            reduction_pct = max(10, reduction_pct - 10)
        else:
            reduction_pct = 20

        prompt = (
            f"The following cheat sheet boxes caused overflow on "
            f"{FORMAT_CONSTRAINTS[paper_format]['description']}.\n"
            f"The content produced {actual_pages} pages but must fit in {expected_pages} page(s).\n\n"
            f"OVERFLOW ERRORS:\n" + "\n".join(f"- {e}" for e in overflow_errors) + "\n\n"
            f"Reduce total content by approximately {reduction_pct}%. Strategies:\n"
            f"- Remove the least important or most redundant examples\n"
            f"- Shorten the most verbose explanations slightly\n"
            f"- Combine small related boxes\n"
            f"- Use inline $...$ math instead of display align* environments\n"
            f"- Keep ALL formulas, key definitions, and most examples\n"
            f"- Do NOT over-reduce — the result should still fill {expected_pages} page(s) completely\n\n"
            f"CURRENT BOXES:\n{current_boxes}\n\n"
            f"Output the condensed boxes in the same %%% BOX: title %%% ... %%% END %%% format."
        )

        response_text = self._stream_response(SYSTEM_PROMPT, prompt)
        new_boxes = _parse_boxes(response_text)
        return new_boxes if new_boxes else boxes
