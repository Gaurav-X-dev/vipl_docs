"""The form's verdict field is the case's verdict.

Every insurer form asks the outcome in its own words — "Report Overall Status",
"Investigation outcome", "Decision" — and tags that field with the ``outcome``
document mapping. The case carries the same answer as ``case.outcome`` for the
dashboards, the TAT tiles and the status machine.

These tests exist because the two were once not connected: an investigator
would fill "Report Overall Status: Positive", press Submit, and be told to set
an outcome they had just set. That must not come back.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.enums import CaseOutcome, CaseStatus, ReportStatus
from app.models.form import FormSection, FormTemplate
from app.services import form_service

API = settings.API_V1_PREFIX


class TestVerdictMapping:
    async def test_every_template_asks_for_an_outcome(self, db, seeded):
        """A form with no verdict field would strand its case at submit."""
        async with seeded() as session:
            result = await session.execute(
                select(FormTemplate).options(
                    selectinload(FormTemplate.sections).selectinload(
                        FormSection.fields
                    )
                )
            )
            templates = result.unique().scalars().all()
            assert templates, "no form templates were seeded"

            without = [
                template.name
                for template in templates
                if not form_service.outcome_fields(template)
            ]
            assert without == [], f"templates with no outcome field: {without}"

    async def test_outcome_fields_offer_the_three_outcomes(self, db, seeded):
        async with seeded() as session:
            result = await session.execute(
                select(FormTemplate).options(
                    selectinload(FormTemplate.sections).selectinload(
                        FormSection.fields
                    )
                )
            )
            expected = {member.value.title() for member in CaseOutcome}
            for template in result.unique().scalars().all():
                for field in form_service.outcome_fields(template):
                    options = {str(o) for o in (field.options or [])}
                    assert expected <= options, (
                        f"{template.name} / {field.field_key} offers {options}"
                    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Positive", CaseOutcome.POSITIVE),
        ("negative", CaseOutcome.NEGATIVE),
        ("  Suspicious  ", CaseOutcome.SUSPICIOUS),
        ("", None),
        (None, None),
        ("Maybe", None),
    ],
)
def test_outcome_parsing(raw, expected):
    assert form_service._parse_outcome(raw) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Final", ReportStatus.FINAL),
        ("interim", ReportStatus.INTERIM),
        ("", None),
        ("Draft", None),
    ],
)
def test_report_status_parsing(raw, expected):
    assert form_service._parse_report_status(raw) is expected


class TestVerdictReachesTheCase:
    """The behaviour a user sees: fill the form, and Submit just works."""

    async def _make_case(self, client: AsyncClient, headers, name: str) -> dict:
        """A fresh case whose company and case type actually have a form.

        The pair is read from the seeded templates rather than hard-coded, so
        the test keeps working as the client's form set changes.
        """
        templates = await client.get(f"{API}/form-templates", headers=headers)
        assert templates.status_code == 200, templates.text
        active = [row for row in templates.json() if row["is_active"]]
        assert active, "no active form template was seeded"
        template = active[0]

        created = await client.post(
            f"{API}/cases",
            json={
                "company_id": template["company_id"],
                "case_type_id": template["case_type_id"],
                "life_assured_name": name,
                "krn_no": f"KRN-{name.replace(' ', '')}",
                "city": "Lucknow",
                "state": "Uttar Pradesh",
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        case = created.json()

        # A real case is always with someone before its form is submitted, so
        # put it on a desk — the status machine will not accept a report from
        # an unassigned case, and rightly so.
        me = await client.get(f"{API}/auth/me", headers=headers)
        assert me.status_code == 200, me.text
        assigned = await client.post(
            f"{API}/cases/{case['id']}/assign",
            json={"assigned_to_id": me.json()["id"]},
            headers=headers,
        )
        assert assigned.status_code == 200, assigned.text
        return case

    async def test_saving_the_form_sets_the_case_outcome(
        self, client: AsyncClient, admin_headers
    ):
        case = await self._make_case(client, admin_headers, "Verdict Draft")
        assert case["outcome"] is None

        form = await client.get(
            f"{API}/cases/{case['id']}/form", headers=admin_headers
        )
        assert form.status_code == 200, form.text
        body = form.json()

        keys = [
            field["field_key"]
            for section in body["template"]["sections"]
            for field in section["fields"]
            if field.get("document_mapping") == "outcome"
        ]
        assert keys, "the attached template has no outcome field"

        saved = await client.put(
            f"{API}/cases/{case['id']}/form",
            json={"values": {keys[-1]: "Suspicious"}, "submit": False},
            headers=admin_headers,
        )
        assert saved.status_code == 200, saved.text

        # A draft save is enough — the case does not wait for submission.
        detail = await client.get(
            f"{API}/cases/{case['id']}", headers=admin_headers
        )
        assert detail.json()["outcome"] == CaseOutcome.SUSPICIOUS.value

    async def test_submit_no_longer_asks_for_an_outcome_twice(
        self, client: AsyncClient, admin_headers
    ):
        case = await self._make_case(client, admin_headers, "Verdict Submit")
        form = await client.get(
            f"{API}/cases/{case['id']}/form", headers=admin_headers
        )
        assert form.status_code == 200, form.text
        body = form.json()

        # Fill every required field, the outcome among them, then submit.
        values: dict[str, str] = {}
        for section in body["template"]["sections"]:
            for field in section["fields"]:
                if not field["is_required"]:
                    continue
                mapping = field.get("document_mapping")
                if mapping == "outcome":
                    values[field["field_key"]] = "Positive"
                elif mapping == "report_status":
                    values[field["field_key"]] = "Final"
                elif field["field_type"] == "DATE":
                    values[field["field_key"]] = "2026-08-28"
                elif field["field_type"] in {"SELECT", "RADIO"}:
                    options = field.get("options") or ["Yes"]
                    values[field["field_key"]] = str(options[0])
                elif field["field_type"] == "YES_NO_NA":
                    values[field["field_key"]] = "YES"
                else:
                    values[field["field_key"]] = "Recorded during the visit"

        submitted = await client.put(
            f"{API}/cases/{case['id']}/form",
            json={"values": values, "submit": True},
            headers=admin_headers,
        )
        assert submitted.status_code == 200, submitted.text

        detail = await client.get(
            f"{API}/cases/{case['id']}", headers=admin_headers
        )
        payload = detail.json()
        assert payload["outcome"] == CaseOutcome.POSITIVE.value
        assert payload["status"] == CaseStatus.REPORT_SUBMITTED.value


class TestClosedCaseFormIsReadOnly:
    """A case that arrived Completed in the client's file is history.

    Letting someone fill in its whole form and only refusing at submit is the
    kind of dead end that wastes an afternoon.
    """

    async def test_completed_case_reports_why_its_form_is_locked(
        self, client: AsyncClient, admin_headers
    ):
        templates = await client.get(f"{API}/form-templates", headers=admin_headers)
        template = next(row for row in templates.json() if row["is_active"])
        created = await client.post(
            f"{API}/cases",
            json={
                "company_id": template["company_id"],
                "case_type_id": template["case_type_id"],
                "life_assured_name": "Closed Case Subject",
                "krn_no": "KRN-CLOSED-1",
            },
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text
        case_id = created.json()["id"]

        # Walk it to Completed the way an imported closed case would sit.
        for target in (
            CaseStatus.ASSIGNED,
            CaseStatus.WIP,
            CaseStatus.RIP,
            CaseStatus.REPORT_SUBMITTED,
            CaseStatus.UNDER_REVIEW,
            CaseStatus.VERIFIED,
            CaseStatus.COMPLETED,
        ):
            moved = await client.post(
                f"{API}/cases/{case_id}/status",
                json={"status": target.value, "outcome": CaseOutcome.POSITIVE.value},
                headers=admin_headers,
            )
            assert moved.status_code == 200, f"{target}: {moved.text}"

        form = await client.get(
            f"{API}/cases/{case_id}/form", headers=admin_headers
        )
        assert form.status_code == 200, form.text
        body = form.json()
        assert body["can_edit"] is False
        assert "Completed" in (body["locked_reason"] or "")
