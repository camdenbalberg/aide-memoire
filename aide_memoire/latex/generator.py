"""Orchestrator: ties extraction → processing → rendering → compilation → verification."""

from pathlib import Path

from rich.console import Console

from aide_memoire.compiler import LatexCompiler
from aide_memoire.config import Config
from aide_memoire.extractors.base import BaseExtractor
from aide_memoire.intel import parse_intel
from aide_memoire.latex.renderer import LatexRenderer
from aide_memoire.models import Sheet
from aide_memoire.processor import ContentProcessor
from aide_memoire.verifier import OverflowVerifier


class CheatSheetGenerator:
    def __init__(self, config: Config):
        self.config = config
        self.processor = ContentProcessor(model=config.model)
        self.renderer = LatexRenderer()
        self.compiler = LatexCompiler()
        self.verifier = OverflowVerifier()
        self.console = Console()

    def generate(self) -> Path:
        """Run the full pipeline and return the path to the output file."""
        # Step 1: Extract content from all input files
        self.console.print("[bold blue]Step 1/5:[/] Extracting content from input files...")
        documents = []
        for f in self.config.input_files:
            f = Path(f)
            self.console.print(f"  Extracting: {f.name}")
            extractor = BaseExtractor.for_file(f)
            doc = extractor.extract(f, output_dir=self.config.output_dir)
            documents.append(doc)
            self.console.print(f"    → {len(doc.blocks)} content blocks extracted")

        total_blocks = sum(len(d.blocks) for d in documents)
        self.console.print(f"  Total: {total_blocks} content blocks from {len(documents)} file(s)")

        # Step 2: Parse intel hints
        intel_hints = []
        if self.config.intel_path:
            self.console.print(f"[bold blue]Step 2/5:[/] Parsing intel hints from {self.config.intel_path}...")
            intel_hints = parse_intel(self.config.intel_path)
            self.console.print(f"  → {len(intel_hints)} hints loaded")
        else:
            self.console.print("[bold blue]Step 2/5:[/] No intel file provided, skipping.")

        # Step 3: Process with Claude API
        self.console.print(f"[bold blue]Step 3/5:[/] Processing content with Claude ({self.config.model})...")
        boxes = self.processor.process(
            documents,
            intel_hints=intel_hints,
            paper_format=self.config.paper_format,
            max_boxes=self.config.max_boxes,
        )
        self.console.print(f"  → {len(boxes)} boxes generated")
        for box in boxes:
            self.console.print(f"    • {box.title}")

        # Step 4: Render LaTeX
        self.console.print("[bold blue]Step 4/5:[/] Generating LaTeX...")
        sheet = Sheet(
            title=self.config.title,
            author=self.config.author,
            paper_format=self.config.paper_format,
            boxes=boxes,
        )
        latex_source = self.renderer.render(sheet)

        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        tex_path = self.config.output_dir / "cheatsheet.tex"
        tex_path.write_text(latex_source, encoding="utf-8")
        self.console.print(f"  → Written to {tex_path}")

        if self.config.no_compile:
            self.console.print("[green]Done! LaTeX generated (compilation skipped).[/]")
            return tex_path

        # Step 5: Compile and verify
        self.console.print("[bold blue]Step 5/5:[/] Compiling LaTeX → PDF...")
        pdf_path = self.compiler.compile(tex_path)
        self.console.print(f"  → Compiled to {pdf_path}")

        if self.config.no_verify:
            self.console.print("[green]Done! PDF generated (verification skipped).[/]")
            return pdf_path

        # Verify with retry loop
        for attempt in range(self.config.max_retries):
            result = self.verifier.verify(pdf_path)
            if result.passed:
                if result.warnings:
                    self.console.print("[yellow]Warnings:[/]")
                    for w in result.warnings:
                        self.console.print(f"  ⚠ {w}")
                self.console.print("[bold green]Verification passed! No overflow detected.[/]")
                return pdf_path

            self.console.print(
                f"[yellow]Overflow detected (attempt {attempt + 1}/{self.config.max_retries}), condensing...[/]"
            )
            for e in result.errors:
                self.console.print(f"  ✗ {e}")

            boxes = self.processor.condense(
                boxes, result.errors, self.config.paper_format
            )
            sheet.boxes = boxes
            latex_source = self.renderer.render(sheet)
            tex_path.write_text(latex_source, encoding="utf-8")
            pdf_path = self.compiler.compile(tex_path)

        self.console.print(
            "[bold red]Warning: Could not fully resolve overflow after "
            f"{self.config.max_retries} attempts. PDF may have issues.[/]"
        )
        return pdf_path
