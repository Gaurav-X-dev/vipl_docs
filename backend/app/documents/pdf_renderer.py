"""PDF output.

Two paths:

1. ``convert_docx`` — when a DOCX has already been generated from the client's
   own template and LibreOffice/Word is available on the host, convert that file
   so the client's exact layout survives into PDF.
2. ``render_report`` — a self-contained ReportLab renderer used when no
   converter is installed, or when the template is the legacy binary ``.doc``.
   It lays the same case data out as a clean, printable report.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#d1d5db")
HEADER_BG = colors.HexColor("#f3f4f6")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocTitle",
            parent=base["Title"],
            fontSize=15,
            leading=19,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontSize=10.5,
            leading=13,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "Label", parent=base["Normal"], fontSize=8.5, leading=11, textColor=MUTED
        ),
        "value": ParagraphStyle(
            "Value", parent=base["Normal"], fontSize=9, leading=12, textColor=INK
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"], fontSize=9, leading=13, textColor=INK
        ),
        "footer": ParagraphStyle(
            "Footer", parent=base["Normal"], fontSize=7.5, leading=10, textColor=MUTED
        ),
    }


def _kv_table(rows: Iterable[tuple[str, Any]], styles: dict) -> Table | None:
    data = [
        [
            Paragraph(str(label), styles["label"]),
            Paragraph("" if value in (None, "") else str(value), styles["value"]),
        ]
        for label, value in rows
    ]
    if not data:
        return None
    table = Table(data, colWidths=[55 * mm, 115 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
            ]
        )
    )
    return table


def _grid_table(headers: list[str], rows: list[list[Any]], styles: dict) -> Table | None:
    if not rows:
        return None
    data = [[Paragraph(f"<b>{h}</b>", styles["label"]) for h in headers]]
    for row in rows:
        data.append([Paragraph("" if c in (None, "") else str(c), styles["value"]) for c in row])
    width = 170 * mm / max(1, len(headers))
    table = Table(data, colWidths=[width] * len(headers), hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.25, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def render_report(
    output_path: Path,
    *,
    title: str,
    subtitle: str,
    header_rows: list[tuple[str, Any]],
    sections: list[dict[str, Any]],
    footer_note: str | None = None,
) -> Path:
    """Render a clean printable report.

    ``sections`` entries take one of three shapes::

        {"title": "...", "rows": [(label, value), ...]}
        {"title": "...", "text": "long narrative"}
        {"title": "...", "headers": [...], "table": [[...], ...]}
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    story: list[Any] = [
        Paragraph(title, styles["title"]),
        Paragraph(subtitle, styles["subtitle"]),
    ]

    header = _kv_table(header_rows, styles)
    if header is not None:
        story.append(header)

    for section in sections:
        block: list[Any] = [Paragraph(section.get("title", ""), styles["section"])]
        if section.get("rows"):
            table = _kv_table(section["rows"], styles)
            if table is not None:
                block.append(table)
        if section.get("headers") and section.get("table"):
            table = _grid_table(section["headers"], section["table"], styles)
            if table is not None:
                block.append(table)
        if section.get("text"):
            for paragraph in str(section["text"]).split("\n"):
                if paragraph.strip():
                    block.append(Paragraph(paragraph.strip(), styles["body"]))
                    block.append(Spacer(1, 3))
        if section.get("page_break_before"):
            story.append(PageBreak())
        story.append(KeepTogether(block) if len(block) <= 6 else block[0])
        if len(block) > 6:
            story.extend(block[1:])

    if footer_note:
        story.append(Spacer(1, 10))
        story.append(Paragraph(footer_note, styles["footer"]))

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )
    document.build(story, onFirstPage=_page_furniture, onLaterPages=_page_furniture)
    return output_path


def _page_furniture(canvas, document) -> None:  # pragma: no cover - drawing only
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(A4[0] - 18 * mm, 7.5 * mm, f"Page {canvas.getPageNumber()}")
    canvas.drawString(18 * mm, 7.5 * mm, "Confidential — investigation report")
    canvas.restoreState()


# --------------------------------------------------------------------------- #
# Optional DOCX -> PDF conversion
# --------------------------------------------------------------------------- #
def find_converter() -> str | None:
    """Locate LibreOffice, if the host has it."""
    for name in ("soffice", "libreoffice", "soffice.exe"):
        path = shutil.which(name)
        if path:
            return path
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def convert_docx(docx_path: Path, output_dir: Path) -> Path | None:
    """Convert a DOCX to PDF, preserving the client's layout. ``None`` if absent."""
    converter = find_converter()
    if converter is None:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                converter,
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(docx_path),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    candidate = output_dir / f"{docx_path.stem}.pdf"
    return candidate if candidate.exists() else None
