"""A generated report must carry our data and nothing else.

The client's forms arrived as *completed* specimen reports. Tagging them by
searching for known values left the tabular answers in place, so every report
we produced shipped with the specimen's findings — "Not shared", "NA", "YES",
"Nearby People" — sitting under our letterhead next to the two fields the
investigator had actually filled.

Two properties are locked down here:

* no specimen answer survives into a template, and therefore into a report;
* every form field the layout can account for becomes a placeholder, so what
  the investigator types is what the client reads.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from app.core.config import settings
from app.documents.table_tagger import (
    TableTagReport,
    build_index,
    find_field,
    normalise,
    row_group,
)

#: Values belonging to the client's specimen reports. None may appear in a
#: tagged template, so none can reach a generated document.
SPECIMEN_VALUES = (
    "Pooja",
    "Ajay Yadav",
    "6167374565",
    "0657197410",
    "Satyapal",
    "Rakesh Kumar Singh",
    "9411844780",
    "8077357398",
    "Mohan Kumar sahu",
    "Kapil Sharma",
    "anita devi",
    "9709189309",
    "70534807",
    "Bhimsen",
    "Nearby People",
    "GEETA AHIRWAR",
    "7827114949",
    "9415142969",
    "9621161085",
)

#: Answers the specimen gave that would read as ours if they survived.
SPECIMEN_ANSWERS = ("Not shared", "Nearby People")


def document_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", "ignore")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", xml))


def tagged_templates() -> list[Path]:
    folder = Path(settings.template_tagged_dir)
    return sorted(folder.glob("*.docx")) if folder.exists() else []


class TestNoSpecimenDataSurvives:
    def test_there_are_tagged_templates(self):
        templates = tagged_templates()
        if not templates:
            pytest.skip(
                "no tagged templates on this machine — run "
                "python -m scripts.retag_templates --confirm"
            )
        assert len(templates) >= 15

    def test_no_template_carries_a_specimen_value(self):
        templates = tagged_templates()
        if not templates:
            pytest.skip("no tagged templates on this machine")

        offenders: list[str] = []
        for path in templates:
            body = document_text(path)
            for value in SPECIMEN_VALUES:
                if value in body:
                    offenders.append(f"{path.name}: {value!r}")
        assert offenders == [], offenders

    def test_no_template_carries_a_specimen_answer(self):
        """The tabular answers are the ones that used to slip through."""
        templates = tagged_templates()
        if not templates:
            pytest.skip("no tagged templates on this machine")

        offenders: list[str] = []
        for path in templates:
            body = document_text(path)
            for answer in SPECIMEN_ANSWERS:
                if answer in body:
                    offenders.append(f"{path.name}: {answer!r}")
        assert offenders == [], offenders

    def test_templates_actually_carry_placeholders(self):
        """A blank template would also pass the checks above, so verify intent."""
        templates = tagged_templates()
        if not templates:
            pytest.skip("no tagged templates on this machine")

        thin: list[str] = []
        for path in templates:
            found = re.findall(r"\{\{\s*[a-zA-Z0-9_]+\s*\}\}", document_text(path))
            if len(found) < 5:
                thin.append(f"{path.name}: {len(found)} placeholder(s)")
        assert thin == [], thin


class TestLabelMatching:
    """The matcher decides what becomes a placeholder and what gets cleared."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("  DOB / Age  ", "dob age"),
            ("3. Place of Birth", "place of birth"),
            ("(12) Marital Status", "marital status"),
            ("Income / Salary (Per Annum)", "income salary per annum"),
            ("", ""),
        ],
    )
    def test_normalise(self, raw, expected):
        assert normalise(raw) == expected

    def test_exact_label_wins(self):
        index = {"life assured name": "la_name_value", "name": "other"}
        assert find_field("Life Assured Name", index) == "la_name_value"

    def test_a_longer_document_question_still_matches(self):
        index = {"marital status": "marital_status_value"}
        assert (
            find_field("Marital Status as declared in the proposal", index)
            == "marital_status_value"
        )

    def test_an_unknown_label_matches_nothing(self):
        """Which is what makes the cell get cleared rather than kept."""
        index = {"life assured name": "la_name_value"}
        assert find_field("Signature of the branch manager", index) is None

    def test_short_labels_do_not_match_loosely(self):
        index = {"age": "age_value"}
        assert find_field("Coverage of the policy", index) is None

    def test_row_group_returns_the_trio(self):
        index = {
            "dob age": "dob_age_value",
            "dob age matching": "dob_age_match",
            "dob age output": "dob_age_output",
        }
        assert row_group("dob_age_value", index) == [
            "dob_age_value",
            "dob_age_match",
            "dob_age_output",
        ]

    def test_row_group_of_a_plain_field_is_itself(self):
        assert row_group("conclusion", {"conclusion": "conclusion"}) == ["conclusion"]


class TestBuildIndex:
    def test_a_suffixed_label_also_answers_to_its_stem(self):
        class Field:
            def __init__(self, key, label):
                self.field_key = key
                self.label = label

        index = build_index(
            [
                Field("dob_value", "DOB / Age"),
                Field("dob_match", "DOB / Age — matching with proposal form"),
            ]
        )
        assert index["dob age"] == "dob_value"
        assert index["dob age matching with proposal form"] == "dob_match"


class TestCoverageReport:
    def test_coverage_is_the_mapped_share(self):
        report = TableTagReport(file="x.docx")
        report.mapped = [("a", "a"), ("b", "b"), ("c", "c")]
        report.blanked = ["d"]
        assert report.coverage == pytest.approx(75.0)

    def test_an_untouched_document_reports_full_coverage(self):
        assert TableTagReport(file="x.docx").coverage == 100.0
