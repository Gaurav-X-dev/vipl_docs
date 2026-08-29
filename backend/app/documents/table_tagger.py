"""Turn a filled specimen form into a template that carries *only our data*.

The insurer documents are completed real reports. The original tagger replaced
the values it could name — the life assured, the dates, the policy numbers —
and left everything else alone. That was the wrong default: the answers sitting
in the table body ("Not shared", "NA", "YES", "Negative", "Nearby People") are
the *specimen's* answers, and they survived into every report we generated. An
investigator who filled two fields still downloaded a document full of somebody
else's findings.

This module fixes that by reading the layout instead of the text. Every client
form is a table of label/answer rows:

    | 3 | DOB / Age | Not shared | Not shared | NA | NA |
      ^serial ^label  ^-------- answer cells ---------^

So: find the label, match it to a field on the case's form template, and write
``{{ field_key }}`` into the answer cells. And — this is the part that matters —
**blank every answer cell we could not match**. An unmapped cell is left empty,
never with the specimen's answer in it. A gap in a report is a visible gap; a
stranger's data wearing our letterhead is a liability.

Headings, instructions, column titles and the surrounding layout are untouched,
so the client still receives their own document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

#: A cell holding one of these is an answer the specimen gave, never a
#: question. When one turns up where a label should be — a stray continuation
#: row — it is cleared rather than treated as the row's question.
SPECIMEN_ANSWERS = frozenset(
    {
        "na",
        "n a",
        "yes",
        "no",
        "positive",
        "negative",
        "suspicious",
        "not shared",
        "not disclosed",
        "not applicable",
        "nil",
        "none",
        "attached",
        "not traceable",
    }
)


def is_specimen_answer(text: str) -> bool:
    return normalise(text) in SPECIMEN_ANSWERS

#: A serial-number cell: "1", "12.", "(3)".
SERIAL = re.compile(r"^[\(\[]?\d{1,3}[\)\].]?$")

#: Column headers that label the answer columns rather than a question.
COLUMN_TITLES = frozenset(
    {
        "output",
        "remarks",
        "remark",
        "matching with proposal form",
        "declared status in proposal form",
        "observation",
        "observations",
        "status",
        "response",
        "answer",
        "details",
        "value",
    }
)


@dataclass(slots=True)
class TableTagReport:
    """Coverage of one document, so a weak mapping is visible rather than silent."""

    file: str
    mapped: list[tuple[str, str]] = dataclass_field(default_factory=list)
    blanked: list[str] = dataclass_field(default_factory=list)
    skipped_headers: int = 0

    @property
    def coverage(self) -> float:
        total = len(self.mapped) + len(self.blanked)
        return (len(self.mapped) / total * 100) if total else 100.0

    def as_lines(self, verbose: bool = False) -> list[str]:
        lines = [
            f"{self.file}: {len(self.mapped)} row(s) mapped, "
            f"{len(self.blanked)} cleared ({self.coverage:.0f}% coverage)"
        ]
        if verbose:
            for label, key in self.mapped[:200]:
                lines.append(f"    {label[:52]:54} -> {{{{ {key} }}}}")
            for label in self.blanked[:200]:
                lines.append(f"    {label[:52]:54} -> (cleared)")
        return lines


# --------------------------------------------------------------------------- #
# Label matching
# --------------------------------------------------------------------------- #
def normalise(text: str) -> str:
    """Loose key for comparing a document label with a form field label."""
    text = re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip().lower()
    text = re.sub(r"^[\(\[]?\d{1,3}[\)\].]?\s*", "", text)  # leading serial
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_index(fields: list) -> dict[str, str]:
    """``normalised label -> field_key`` for one form template.

    Row-group fields (``dob_value`` / ``dob_match`` / ``dob_output``) share a
    label prefix; the suffix variants are indexed separately so a three-column
    row can fill all three.
    """
    index: dict[str, str] = {}
    for entry in fields:
        key = entry.field_key
        label = normalise(entry.label)
        if label and label not in index:
            index[label] = key
        # "DOB / Age — matching with proposal form" also answers to "dob / age".
        base = re.split(r"\s+(?:—|-)\s+", entry.label, maxsplit=1)[0]
        base_norm = normalise(base)
        if base_norm and base_norm not in index:
            index[base_norm] = key
    return index


def find_field(label: str, index: dict[str, str]) -> str | None:
    """Exact match first, then a contained match for reworded questions."""
    key = normalise(label)
    if not key:
        return None
    if key in index:
        return index[key]
    # The document often carries a longer question than the form's label.
    candidates = [
        (len(indexed), field_key)
        for indexed, field_key in index.items()
        if len(indexed) >= 8 and (indexed in key or key in indexed)
    ]
    if candidates:
        return max(candidates)[1]
    return None


def row_group(field_key: str, index: dict[str, str]) -> list[str]:
    """The ``_value`` / ``_match`` / ``_output`` trio a row may need."""
    for suffix in ("_value", "_match", "_output"):
        if field_key.endswith(suffix):
            stem = field_key[: -len(suffix)]
            break
    else:
        return [field_key]
    keys = set(index.values())
    return [
        candidate
        for candidate in (f"{stem}_value", f"{stem}_match", f"{stem}_output")
        if candidate in keys
    ]


# --------------------------------------------------------------------------- #
# Cell handling
# --------------------------------------------------------------------------- #
def distinct_cells(row) -> list[_Cell]:
    """Row cells with merged duplicates collapsed to one entry."""
    seen: set[int] = set()
    cells: list[_Cell] = []
    for cell in row.cells:
        marker = id(cell._tc)
        if marker in seen:
            continue
        seen.add(marker)
        cells.append(cell)
    return cells


def set_cell(cell: _Cell, text: str) -> None:
    """Replace a cell's contents, keeping its first run's formatting."""
    paragraphs = cell.paragraphs or []
    if not paragraphs:
        cell.text = text
        return
    first: Paragraph = paragraphs[0]
    if first.runs:
        first.runs[0].text = text
        for run in first.runs[1:]:
            run.text = ""
    else:
        first.text = text
    for extra in paragraphs[1:]:
        for run in extra.runs:
            run.text = ""


def cell_text(cell: _Cell) -> str:
    return re.sub(r"\s+", " ", cell.text.replace(" ", " ")).strip()


#: Below this length, repeated identical text across a row is an answer the
#: specimen gave ("Not shared", "NA"), not a section banner.
BANNER_MIN_LENGTH = 20


def is_section_header(cells: list[_Cell]) -> bool:
    """A banner row spanning the table.

    A real banner is a merged cell, which :func:`distinct_cells` has already
    collapsed to one entry. Several separate cells carrying the same short
    string are not a heading — they are the specimen answering the same way
    six times, and treating that as a banner is how "Not shared" survived a
    whole row.
    """
    if len(cells) <= 1:
        return True
    texts = {cell_text(cell) for cell in cells}
    if len(texts) > 1:
        return False
    only = next(iter(texts), "")
    return len(only) >= BANNER_MIN_LENGTH


def looks_like_column_titles(cells: list[_Cell]) -> bool:
    texts = [normalise(cell_text(cell)) for cell in cells]
    titled = [t for t in texts if t in COLUMN_TITLES]
    return len(titled) >= max(1, len(texts) - 2) and len(titled) >= 2


# --------------------------------------------------------------------------- #
# The pass
# --------------------------------------------------------------------------- #
def _nested(cells: list[_Cell]) -> list[Table]:
    tables: list[Table] = []
    for cell in cells:
        tables.extend(cell.tables)
    return tables


def _tag_vertical(
    table: Table, index: dict[str, str], report: TableTagReport
) -> set[int]:
    """Handle the header-above-values layout, returning the rows it consumed.

    Some forms run their questions across the top and the answers underneath:

        | Agency Name | Investigator | Contact | Assignment date |
        | Virtual …   | Satyapal     | 9161…   | 22.07.2026      |

    Read row-wise, "Virtual …" would be taken for a question. So when a row's
    cells nearly all match field labels and the row below matches none, that
    pair is mapped column by column.

    Only the pairs that actually look like this are claimed — the rest of the
    table still goes through the ordinary label/answer pass, because most
    forms mix both shapes in one table.
    """
    consumed: set[int] = set()
    if len(table.rows) < 2:
        return consumed

    rows = list(table.rows)
    position = 0
    while position < len(rows) - 1:
        header = distinct_cells(rows[position])
        values = distinct_cells(rows[position + 1])
        # Three or more questions side by side is what makes this shape
        # recognisable; two could just as easily be a label and its answer.
        if len(header) < 3 or len(header) != len(values):
            position += 1
            continue

        matches = [find_field(cell_text(cell), index) for cell in header]
        named = [m for m in matches if m]
        below = [m for m in (find_field(cell_text(c), index) for c in values) if m]
        if len(named) < len(header) - 1 or below:
            # Either the top row is not all questions, or the bottom row reads
            # as questions too — in which case this is an ordinary table.
            position += 1
            continue

        for key, answer, label in zip(matches, values, header, strict=False):
            if key:
                set_cell(answer, f"{{{{ {key} }}}}")
                report.mapped.append((cell_text(label), key))
            elif cell_text(answer):
                set_cell(answer, "")
                report.blanked.append(cell_text(label))
        consumed.update({position, position + 1})
        position += 2
    return consumed


def tag_tables(
    tables: list[Table], index: dict[str, str], report: TableTagReport
) -> None:
    for table in tables:
        consumed = _tag_vertical(table, index, report)

        for number, row in enumerate(table.rows):
            cells = distinct_cells(row)

            # Always descend: several client forms wrap their whole body in a
            # single outer cell, and the real questions live one level down.
            inner = _nested(cells)
            if inner:
                tag_tables(inner, index, report)

            if number in consumed:
                continue
            if is_section_header(cells):
                report.skipped_headers += 1
                continue

            position = 0
            if position < len(cells) and SERIAL.match(cell_text(cells[position])):
                position += 1
            if position >= len(cells) - 1:
                # Nothing but a serial and one cell: not a label/answer row.
                continue

            label_cell = cells[position]
            label = cell_text(label_cell)
            answers = cells[position + 1 :]
            if not label:
                continue
            if is_specimen_answer(label):
                # An answer sitting where a question should be: a continuation
                # row the specimen filled in. Nothing of ours belongs here.
                set_cell(label_cell, "")
                for answer in answers:
                    if cell_text(answer):
                        set_cell(answer, "")
                report.blanked.append(label)
                continue
            if not answers:
                continue
            if looks_like_column_titles([label_cell, *answers]):
                report.skipped_headers += 1
                continue

            matched = find_field(label, index)
            if matched is None:
                # No field owns this row, so nothing of ours belongs here.
                # Clearing it is the whole point: the specimen's answer must
                # not travel out under our name.
                for answer in answers:
                    if cell_text(answer):
                        set_cell(answer, "")
                report.blanked.append(label)
                continue

            keys = row_group(matched, index)
            for offset, answer in enumerate(answers):
                key = keys[offset] if offset < len(keys) else None
                set_cell(answer, f"{{{{ {key} }}}}" if key else "")
            report.mapped.append((label, matched))
