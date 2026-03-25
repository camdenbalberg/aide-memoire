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
You are an expert at creating comprehensive, scannable exam reference cards (cheat sheets) in LaTeX.

Your job: take extracted course material and produce the INNER CONTENT of LaTeX boxes for a cheat sheet.
You do NOT produce the full LaTeX document — only the content that goes inside each box.

STRUCTURE — THIS IS THE MOST IMPORTANT RULE:
The content must be EASY TO SCAN QUICKLY during an exam. This means:
- Put EACH definition, rule, or concept on its OWN line, separated by \\\\ (line breaks).
- Start each line with \\textbf{Term:} followed by the definition/explanation.
- Use \\ctitle{Subtitle} to create sub-sections within a box for logical grouping.
- NEVER write wall-of-text paragraphs. A student must be able to glance at the sheet and
  instantly find the specific formula or definition they need.

Here is an EXAMPLE of the correct structure:

\\ctitle{Key Definitions}
\\textbf{Sample Space (S):} The set of all possible outcomes of a random process. For a die, $S = \\{1,2,3,4,5,6\\}$.\\\\
\\textbf{Event:} A subset of outcomes from S. The event "rolling even" is $A = \\{2,4,6\\}$.\\\\
\\textbf{Probability:} $P(A)$ is a value between 0 and 1 measuring how likely event A is to occur.\\\\
\\ctitle{Rules}
\\textbf{Complement Rule:} $P(A^c) = 1 - P(A)$. Use this for "at least one" problems.\\\\
\\textbf{Addition Rule:} $P(A \\cup B) = P(A) + P(B) - P(A \\cap B)$.\\\\
\\textbf{Example:} $P(\\text{King or Heart}) = \\frac{4}{52} + \\frac{13}{52} - \\frac{1}{52} = \\frac{16}{52}$.

NOTICE: Each concept gets its own line. Bold term first. Formula inline. Explanation after.

CONTENT REQUIREMENTS:
- The cheat sheet must be thorough enough that any student can use it to do well on the exam.
- Write COMPLETE definitions — not single-word fragments, but also not long paragraphs.
  Good: "The set of all possible outcomes of a random process."
  Bad: "All possible outcomes" (too short, unclear)
  Bad: "The sample space, denoted S, is defined as the complete collection of every single..." (too wordy)
- Include WORKED EXAMPLES with actual numbers for major formulas. Show setup and answer on one line.
- Include step-by-step procedures where relevant (Step 1, Step 2, etc.), each step on its own line.
- Include "Watch out:" or "Tip:" notes for common mistakes.
- Each definition line should use most of the available width — if it ends far before the right
  edge, add more explanatory detail.

FORMATTING RULES:
- Content is wrapped in {\\scriptsize ...} with tight line spacing — the template handles this.
- Use \\textbf{} for bold terms. Use \\textit{} for emphasis.
- Use \\ctitle{Subtitle} for sub-headings (creates centered underlined bold heading).
- For math: prefer inline $...$ for single formulas. Only use \\begin{align*} for MULTIPLE
  aligned equations. Display math adds large vertical gaps.
- For tables: \\setlength\\tabcolsep{2pt} then \\begin{tabular}{cols}...\\end{tabular}.
  Use p{<width>} columns for wrapping text.
- For bullet lists: \\begin{itemize}[leftmargin=*,topsep=0pt,itemsep=0pt,parsep=0pt]
- Use \\\\ for line breaks between definitions/concepts (NOT to create blank lines).
- Do NOT use \\vspace, \\begin{spacing}, \\section, or preamble commands.
- Do NOT use $$ ... $$ for display math.

LaTeX SAFETY:
- & is ONLY allowed inside tabular/align environments. Everywhere else use \\&.
- In \\ctitle{} arguments: escape & as \\&.
- Do NOT produce \\begin{document}, \\documentclass, or preamble.

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
        f"CRITICAL REMINDERS:\n"
        f"- Each definition/rule/concept goes on its OWN line with \\\\ at the end.\n"
        f"- Start each line with \\textbf{{Term:}} then the definition.\n"
        f"- Use \\ctitle{{}} for sub-sections within boxes.\n"
        f"- Do NOT write wall-of-text paragraphs — this is a REFERENCE CARD, not an essay.\n"
        f"- Include worked examples with actual numbers.\n"
        f"- A student must be able to scan and find any concept in seconds."
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
