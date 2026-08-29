"""Generate the sample import files under ``samples/``.

Writes ``case_import_template.xlsx`` and ``case_import_template.csv`` with the
exact header row the importer expects (derived from the client's Image 3) plus a
few illustrative rows using invented data.

Usage (from ``backend/``)::

    python -m scripts.make_samples
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import PROJECT_ROOT  # noqa: E402
from app.seeds.catalogue import IMPORT_COLUMNS  # noqa: E402
from app.services import export_service  # noqa: E402

#: The 18 columns that appear in the client's daily file, in their order.
CORE_COLUMNS = [
    "Co. Name",
    "Case Type",
    "Month",
    "Date",
    "Aging",
    "KRN No",
    "Policy Number",
    "Application Number",
    "Life_Assured_Name",
    "City",
    "State",
    "Assign To",
    "Status",
    "Remark/ADD IO ID",
    "Pin Code",
    "Report Date",
    "Completion Date",
    "Report Prep By",
]

SAMPLE_ROWS: list[list[object]] = [
    [
        "ICICI", "Pre Issuance", "Aug-2026", "05-08-2026", 3, "1180101",
        "K9500011", "", "Ramesh Chandra Yadav", "Lucknow", "Uttar Pradesh",
        "Rahul Sharma", "Assigned", "Fresh allocation", "226016", "", "", "",
    ],
    [
        "HDFC", "Profile Check", "Aug-2026", "06-08-2026", 2, "1180102",
        "PP000921", "1001180001", "Mohammad Arif", "Meerut", "Uttar Pradesh",
        "Anita Verma", "WIP", "", "250001", "", "", "",
    ],
    [
        "Bajaj", "Death Claim", "Aug-2026", "01-08-2026", 7, "1180103",
        "0602911010", "", "Suresh Prajapati", "Noida", "Uttar Pradesh",
        "Imran Qureshi", "Report in progress", "Nominee statement pending",
        "201301", "", "", "",
    ],
    [
        "Kotak", "Pre Claim", "Jul-2026", "28-07-2026", 12, "1180104",
        "80399120", "", "Deepak Rathore", "Jodhpur", "Rajasthan", "",
        "Unassigned", "Awaiting allocation", "342001", "", "", "",
    ],
    [
        "Canara HSBC", "Pre Issuance", "Jul-2026", "22-07-2026", 18, "1180105",
        "9103990011", "", "Harish Verma", "Mathura", "Uttar Pradesh",
        "Rahul Sharma", "Completed", "Positive closure", "281301",
        "05-08-2026", "05-08-2026", "Kapil Sharma",
    ],
]


def build_notes() -> str:
    lines = [
        "# Import mapping notes",
        "",
        "The importer resolves spreadsheet headers to internal fields through the",
        "`VIPL_STANDARD_V1` import template, which lives in the database",
        "(`import_templates` / `import_column_mappings`). Header text is matched",
        "case-insensitively and ignoring punctuation and spacing, so",
        "`Life_Assured_Name`, `Life Assured Name` and `life assured name` all match.",
        "",
        "## Columns",
        "",
        "| Excel column | Internal field | Type | Required | Also accepted |",
        "|--------------|----------------|------|----------|---------------|",
    ]
    for column in IMPORT_COLUMNS:
        aliases = ", ".join(column.aliases) if column.aliases else "—"
        lines.append(
            f"| {column.source_column} | `{column.target_field}` | "
            f"{column.data_type} | {'yes' if column.is_required else 'no'} | "
            f"{aliases} |"
        )
    lines += [
        "",
        "## Rules",
        "",
        "* **Dates** are read day-first: `05-08-2026` is 5 August 2026. `dd-mm-yyyy`,",
        "  `dd/mm/yyyy`, `dd.mm.yyyy`, ISO dates and Excel serial numbers all work.",
        "* **Company** and **Case Type** must resolve to an active record. Both accept",
        "  the aliases listed above, so `Bajaj`, `Bajaj Allianz` and `BAJAJ` all map to",
        "  the same company.",
        "* Either **Policy Number** or **Application Number** is required.",
        "* **Assign To** is matched to staff by employee code, then email, then full",
        "  name. If no match is found the case is imported unassigned and the row is",
        "  flagged as a warning, not an error.",
        "* **Status** is mapped through a synonym table (`WIP`, `Work in progress`,",
        "  `In Progress` all become WIP). Unrecognised values produce a warning and the",
        "  case is created as Imported.",
        "* **Duplicates** are detected on `(Co. Name, KRN No)`; when KRN is blank the",
        "  fallback key is `(Co. Name, Policy Number, Application Number,",
        "  Life_Assured_Name)`.",
        "* Uploading a file whose SHA-256 checksum matches an already-committed batch",
        "  is refused, so the same file cannot be imported twice by accident.",
        "* Extra columns are preserved in the row snapshot and ignored for mapping.",
        "",
        "## Workflow",
        "",
        "```",
        "Upload -> Detect headers -> Validate structure -> Preview -> Map columns",
        "       -> Validate data -> Show errors -> Confirm -> Create cases -> Summary",
        "```",
        "",
        "Rejected rows can be downloaded as a workbook containing the row number, the",
        "original data and the error message.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    samples_dir = PROJECT_ROOT / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    xlsx = export_service.to_xlsx(
        CORE_COLUMNS, SAMPLE_ROWS, sheet_title="Cases", freeze_header=True
    )
    (samples_dir / "case_import_template.xlsx").write_bytes(xlsx)

    csv_bytes = export_service.to_csv(CORE_COLUMNS, SAMPLE_ROWS)
    (samples_dir / "case_import_template.csv").write_bytes(csv_bytes)

    (samples_dir / "import_mapping_notes.md").write_text(
        build_notes(), encoding="utf-8"
    )

    print(f"Wrote sample files to {samples_dir}")
    for name in (
        "case_import_template.xlsx",
        "case_import_template.csv",
        "import_mapping_notes.md",
    ):
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
