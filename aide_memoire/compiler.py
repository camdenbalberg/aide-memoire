"""LaTeX compilation wrapper."""

import subprocess
from pathlib import Path


class CompilationError(Exception):
    """Raised when pdflatex fails."""
    pass


class LatexCompiler:
    def compile(self, tex_path: Path, output_dir: Path | None = None) -> Path:
        """Compile .tex to .pdf using pdflatex. Returns path to PDF."""
        output_dir = output_dir or tex_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run pdflatex twice for cross-references
        for run in range(2):
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    f"-output-directory={output_dir}",
                    str(tex_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(tex_path.parent),
            )
            if result.returncode != 0 and run == 1:
                # Only raise on the second pass — first pass may have warnings
                errors = self._parse_errors(result.stdout)
                if errors:
                    raise CompilationError(
                        f"pdflatex failed:\n" + "\n".join(errors)
                    )

        pdf_path = output_dir / tex_path.with_suffix(".pdf").name
        if not pdf_path.exists():
            raise CompilationError(
                f"PDF not generated at {pdf_path}. "
                f"pdflatex output:\n{result.stdout[-1000:]}"
            )
        return pdf_path

    def _parse_errors(self, log_text: str) -> list[str]:
        """Extract error lines from pdflatex log output."""
        errors = []
        for line in log_text.splitlines():
            if line.startswith("!") or "Fatal error" in line:
                errors.append(line)
        return errors
