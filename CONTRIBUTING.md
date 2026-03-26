# Contributing to aide-memoire

Thanks for your interest in contributing! Bug reports, new extractors, template improvements, and feature ideas are all welcome.

## Development Setup

```bash
git clone https://github.com/camdenbalberg/aide-memoire.git
cd aide-memoire
python -m venv .venv
.venv/Scripts/activate    # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e .
```

You'll also need:
- `pdflatex` on PATH (TeX Live or MiKTeX)
- `ANTHROPIC_API_KEY` environment variable set

## Ways to Contribute

### Add a new extractor
Subclass `BaseExtractor` in `aide_memoire/extractors/`, implement `extract()`, and register the file extension in `base.py`'s factory method.

### Improve LaTeX templates
Templates live in `aide_memoire/latex/templates/`. They use Jinja2 with TikZ styling. If you have a better layout or a new format (A4, index card, etc.), open a PR.

### Report bugs
Open an issue with:
- Input file types used
- The error output or unexpected behavior
- Your OS, Python version, and LaTeX distribution

## Pull Requests

- Keep PRs focused on a single change
- Test with real course materials if touching extraction or rendering logic
- Update the README if adding new CLI options or formats

## Code Style

- Follow existing patterns
- Use type hints
- Keep the pipeline stages cleanly separated (extract → process → render → compile → verify)
