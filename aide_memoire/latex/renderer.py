"""Jinja2-based LaTeX renderer with custom delimiters."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from aide_memoire.models import PaperFormat, Sheet

TEMPLATE_MAP = {
    PaperFormat.LETTER_3COL: "letter_3col.tex.j2",
    PaperFormat.LETTER_4COL: "letter_4col.tex.j2",
    PaperFormat.NOTECARD: "notecard.tex.j2",
}


def _latex_escape_title(text: str) -> str:
    """Escape special LaTeX characters in box titles (not in content)."""
    # Only escape characters that are problematic in TikZ node text
    text = text.replace("&", r"\&")
    text = text.replace("%", r"\%")
    text = text.replace("#", r"\#")
    text = text.replace("_", r"\_")
    return text


class LatexRenderer:
    def __init__(self):
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            # Custom delimiters to avoid LaTeX brace conflicts
            block_start_string="<%",
            block_end_string="%>",
            variable_start_string="<<",
            variable_end_string=">>",
            comment_start_string="<#",
            comment_end_string="#>",
            autoescape=False,
        )
        self.env.filters["latex_escape"] = _latex_escape_title

    def render(self, sheet: Sheet) -> str:
        """Render a Sheet into a complete LaTeX document string."""
        template_name = TEMPLATE_MAP[sheet.paper_format]
        template = self.env.get_template(template_name)
        return template.render(sheet=sheet)
