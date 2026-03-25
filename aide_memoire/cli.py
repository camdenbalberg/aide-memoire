"""CLI interface for aide-memoire."""

from pathlib import Path

import click
from rich.console import Console

from aide_memoire.compiler import CompilationError, LatexCompiler
from aide_memoire.config import Config
from aide_memoire.models import PaperFormat
from aide_memoire.verifier import OverflowVerifier

console = Console()

FORMAT_MAP = {
    "letter-3col": PaperFormat.LETTER_3COL,
    "letter-4col": PaperFormat.LETTER_4COL,
    "notecard": PaperFormat.NOTECARD,
}


@click.group()
def cli():
    """aide-memoire: Generate exam reference cards from course materials."""
    pass


@cli.command()
@click.argument("input_files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--format", "-f", "paper_format",
    type=click.Choice(["letter-3col", "letter-4col", "notecard"]),
    default="letter-3col",
    help="Output paper format.",
)
@click.option("--title", "-t", default=None, help="Cheat sheet title.")
@click.option("--author", "-a", default=None, help="Author name.")
@click.option("--intel", "-i", type=click.Path(exists=True), default=None, help="Path to intel.txt.")
@click.option("--output", "-o", type=click.Path(), default="output", help="Output directory.")
@click.option("--no-compile", is_flag=True, help="Generate LaTeX only, skip compilation.")
@click.option("--no-verify", is_flag=True, help="Skip overflow verification.")
@click.option("--max-boxes", type=int, default=None, help="Maximum number of boxes.")
@click.option("--pages", type=int, default=2, help="Number of pages (e.g., 2 for front and back).")
@click.option("--model", default="claude-sonnet-4-20250514", help="Claude model for processing.")
def generate(input_files, paper_format, title, author, intel, output, no_compile, no_verify, max_boxes, pages, model):
    """Generate a cheat sheet from input files."""
    from aide_memoire.latex.generator import CheatSheetGenerator

    # Build config
    config = Config(
        input_files=[Path(f) for f in input_files],
        output_dir=Path(output),
        paper_format=FORMAT_MAP[paper_format],
        title=title or "Exam Review Sheet",
        author=author or "",
        intel_path=Path(intel) if intel else None,
        model=model,
        max_boxes=max_boxes,
        expected_pages=pages,
        no_compile=no_compile,
        no_verify=no_verify,
    )

    console.print(f"[bold]Generating {paper_format} cheat sheet...[/]")
    try:
        generator = CheatSheetGenerator(config)
        result_path = generator.generate()
        console.print(f"\n[bold green]Output: {result_path}[/]")
    except CompilationError as e:
        console.print(f"[bold red]Compilation failed:[/]\n{e}")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1)


@cli.command("compile")
@click.argument("tex_file", type=click.Path(exists=True))
def compile_cmd(tex_file):
    """Compile a .tex file to PDF."""
    compiler = LatexCompiler()
    try:
        pdf_path = compiler.compile(Path(tex_file))
        console.print(f"[bold green]Compiled: {pdf_path}[/]")
    except CompilationError as e:
        console.print(f"[bold red]Compilation failed:[/]\n{e}")
        raise SystemExit(1)


@cli.command()
@click.argument("pdf_file", type=click.Path(exists=True))
@click.option("--expected-pages", type=int, default=1, help="Expected number of pages.")
def verify(pdf_file, expected_pages):
    """Verify a compiled PDF for overflow issues."""
    verifier = OverflowVerifier()
    result = verifier.verify(Path(pdf_file), expected_pages=expected_pages)

    if result.passed:
        console.print("[bold green]Verification passed![/]")
    else:
        console.print("[bold red]Verification failed:[/]")
        for e in result.errors:
            console.print(f"  x {e}")

    if result.warnings:
        console.print("[yellow]Warnings:[/]")
        for w in result.warnings:
            console.print(f"  - {w}")
