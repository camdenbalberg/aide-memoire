"""Parser for intel.txt hint files."""

from pathlib import Path


def parse_intel(intel_path: Path) -> list[str]:
    """Parse intel.txt into a list of hint strings.

    Expected format:
        # Comments start with #
        IMPORTANT: Chapter 3 hypothesis testing formulas
        NOT ON EXAM: Bayesian statistics section
        FOCUS: z-test vs t-test comparison table
    """
    if not intel_path.exists():
        return []
    hints = []
    for line in intel_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            hints.append(line)
    return hints
