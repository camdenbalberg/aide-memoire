# aide-memoire

Generate dense, single-page exam reference cards (cheat sheets) from course materials using LaTeX.

Feed in your lecture slides, PDFs, Word docs, and text notes — aide-memoire extracts the content, uses Claude to distill it into organized topic boxes, and outputs a professionally typeset LaTeX PDF ready for your exam.

## Features

- **Multi-format input**: `.pptx`, `.pdf`, `.docx`, `.txt` — extracts text, tables, math, and images
- **AI-powered summarization**: Uses Claude to organize and condense content into dense LaTeX boxes
- **Intel hints**: Provide an `intel.txt` file with exam topic hints to guide prioritization
- **Three output formats**:
  - `letter-3col` — 8.5×11" landscape, 3 columns (default)
  - `letter-4col` — 8.5×11" landscape, 4 columns
  - `notecard` — 4×6" notecard, 2 columns
- **Overflow detection**: Automatically verifies the PDF fits on one page and condenses if needed
- **LaTeX quality**: TikZ-styled boxes with titled sections, math rendering, tables, and code listings

## Requirements

- Python 3.12+
- `pdflatex` on PATH (TeX Live, MiKTeX, or similar)
- `ANTHROPIC_API_KEY` environment variable set

## Installation

```bash
git clone https://github.com/camdenbalberg/aide-memoire.git
cd aide-memoire
pip install -e .
```

## Usage

### Generate a cheat sheet

```bash
aide-memoire generate lecture_slides.pptx exam_review.pdf -t "Final Exam Review"
```

### Options

```
aide-memoire generate [OPTIONS] INPUT_FILES...

  --format, -f    Output format: letter-3col, letter-4col, notecard (default: letter-3col)
  --title, -t     Cheat sheet title (default: "Exam Review Sheet")
  --author, -a    Author name
  --intel, -i     Path to intel.txt with exam topic hints
  --output, -o    Output directory (default: output/)
  --no-compile    Generate LaTeX only, skip PDF compilation
  --no-verify     Skip overflow verification
  --max-boxes     Maximum number of content boxes
  --model         Claude model to use (default: claude-sonnet-4-20250514)
```

### Compile an existing .tex file

```bash
aide-memoire compile output/cheatsheet.tex
```

### Verify a PDF for overflow

```bash
aide-memoire verify output/cheatsheet.pdf --expected-pages 1
```

## Intel file format

Create a plain text file with exam topic hints to guide content prioritization:

```
# Lines starting with # are comments
Probability distributions — especially normal, binomial
Hypothesis testing steps
Confidence intervals
Regression formulas and interpretation
```

## How it works

1. **Extract** — Parses input files into content blocks (text, tables, math, images)
2. **Process** — Sends content to Claude with format constraints and intel hints; Claude returns organized LaTeX boxes
3. **Render** — Injects boxes into Jinja2 LaTeX templates with TikZ styling
4. **Compile** — Runs `pdflatex` to produce the PDF
5. **Verify** — Checks page count and text positioning for overflow; auto-condenses and retries if needed (up to 3 attempts)

## Project structure

```
aide_memoire/
├── cli.py                  # Click CLI commands
├── config.py               # Configuration dataclass
├── models.py               # Data models (ContentBlock, Box, Sheet)
├── processor.py            # Claude API content processing
├── compiler.py             # pdflatex wrapper
├── verifier.py             # Overflow detection
├── intel.py                # Intel hint file parser
├── extractors/
│   ├── base.py             # Base extractor with factory method
│   ├── pptx_extractor.py   # PowerPoint extraction
│   ├── pdf_extractor.py    # PDF extraction (PyMuPDF)
│   ├── docx_extractor.py   # Word document extraction
│   └── text_extractor.py   # Plain text reader
└── latex/
    ├── generator.py        # Pipeline orchestrator
    ├── renderer.py         # Jinja2 template renderer
    └── templates/          # LaTeX templates (.tex.j2)
```

## License

MIT
