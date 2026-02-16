"""Markdown-to-PDF converter with Cyrillic support."""

import logging
import re
from pathlib import Path

from fpdf import FPDF

logger = logging.getLogger(__name__)

# Cyrillic-capable font paths (macOS)
_FONT_PATHS = [
    # macOS
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    # Linux
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
]

_BOLD_FONT_PATHS = [
    # macOS
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/Library/Fonts/Arial Bold.ttf"),
    # Linux
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
]


def _find_font(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def _mcell(pdf: FPDF, w: int, h: int, text: str) -> None:
    """multi_cell wrapper that resets x to left margin after each call."""
    pdf.multi_cell(w=w, h=h, text=text, new_x="LMARGIN", new_y="NEXT")


def markdown_to_pdf(text: str, title: str = "") -> bytes:
    """Convert markdown text to PDF bytes.

    Supports: headings (#, ##, ###), bold (**text**), bullet lists (- item),
    and plain paragraphs. All text is Cyrillic-safe.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Register Unicode font
    regular_font = _find_font(_FONT_PATHS)
    bold_font = _find_font(_BOLD_FONT_PATHS)

    if regular_font:
        pdf.add_font("CustomFont", "", str(regular_font))
        if bold_font:
            pdf.add_font("CustomFont", "B", str(bold_font))
        else:
            pdf.add_font("CustomFont", "B", str(regular_font))
        font_family = "CustomFont"
    else:
        font_family = "Helvetica"
        logger.warning("No Cyrillic TTF font found, falling back to Helvetica")

    # Title
    if title:
        pdf.set_font(font_family, "B", 16)
        _mcell(pdf, 0, 8, title)
        pdf.ln(4)

    # Parse and render markdown lines
    for line in text.split("\n"):
        stripped = line.strip()

        if not stripped:
            pdf.ln(3)
            continue

        # Headings
        if stripped.startswith("### "):
            pdf.set_font(font_family, "B", 12)
            _mcell(pdf, 0, 6, stripped[4:])
            pdf.ln(2)
        elif stripped.startswith("## "):
            pdf.set_font(font_family, "B", 13)
            _mcell(pdf, 0, 7, stripped[3:])
            pdf.ln(2)
        elif stripped.startswith("# "):
            pdf.set_font(font_family, "B", 15)
            _mcell(pdf, 0, 8, stripped[2:])
            pdf.ln(3)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            # Bullet list item
            pdf.set_font(font_family, "", 10)
            bullet_text = _strip_bold(stripped[2:])
            _mcell(pdf, 0, 5, "  -  " + bullet_text)
        elif stripped.startswith("---") or stripped.startswith("==="):
            # Horizontal rule
            pdf.ln(2)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(3)
        else:
            # Regular paragraph
            pdf.set_font(font_family, "", 10)
            clean = _strip_bold(stripped)
            _mcell(pdf, 0, 5, clean)

    return pdf.output()


def _strip_bold(text: str) -> str:
    """Remove **bold** markers from text."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)
