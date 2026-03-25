"""LaTeX compilation wrapper."""

import subprocess
from pathlib import Path


class CompilationError(Exception):
    """Raised when pdflatex fails."""
    pass


class LatexCompiler:
    def compile(self, tex_path: Path, output_dir: Path | None = None) -> Path:
        """Compile .tex to .pdf using pdflatex. Returns path to PDF."""
        # Resolve to absolute paths to avoid cwd/relative path confusion
        tex_path = tex_path.resolve()
        output_dir = (output_dir or tex_path.parent).resolve()
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
                encoding="utf-8",
                errors="replace",
            )

        pdf_path = output_dir / tex_path.with_suffix(".pdf").name
        if not pdf_path.exists():
            # Only raise if no PDF was produced at all
            stdout = result.stdout or ""
            errors = self._parse_errors(stdout)
            raise CompilationError(
                f"pdflatex failed (no PDF produced):\n" + "\n".join(errors)
            )

        # Warn about non-fatal errors but don't raise
        self.warnings = self._parse_errors(result.stdout or "")
        return pdf_path

    def _parse_errors(self, log_text: str) -> list[str]:
        """Extract error lines from pdflatex log output."""
        errors = []
        for line in log_text.splitlines():
            if line.startswith("!") or "Fatal error" in line:
                errors.append(line)
        return errors
