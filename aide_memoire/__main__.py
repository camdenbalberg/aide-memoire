"""Entry point for python -m aide_memoire."""

import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from aide_memoire.cli import cli

if __name__ == "__main__":
    cli()
