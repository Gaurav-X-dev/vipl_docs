"""The investigation form flow, end to end, with no dead ends.

Four things this locks down, each of which broke a real working day:

* a field key appears once per template, so filling one answer does not fill
  another field wearing the same key;
* client-supplied values are editable — the lock-and-ask-an-admin step is gone;
* pressing Submit on a freshly assigned case works, instead of refusing with
  "Cannot move from Assigned to Submitted by Investigator";
* an empty required field is named *and located*, so nobody hunts through a
  200-field insurer report for the one thing they missed.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.enums import CaseStatus
from app.models.form import FormSection, FormTemplate
from app.services.case_workflow import path_to

API = settings.API_V1_PREFIX


class TestFieldKeysAreUnique:
    async def test_no_template_repeats_a_field_key(self, db, seeded):
        """Answers are stored per key, so a repeat is one answer in two places."""
        async with seeded() as session:
            result = await session.execute(
                select(FormTemplate).options(
                    selectinload(FormTemplate.sections).selectinload(
                        FormSection.fields
                    )
                )
            )
            offenders: list[str] = []
            for template in result.unique().scalars().all():
                seen: set[str] = set()
                for section in template.sections:
                    for field in section.fields:
                        if field.field_key in seen:
                            offenders.append(
                                f"{template.name}: '{field.field_key}' repeats "
                                f"in section '{section.key}'"
                            )
                        seen.add(field.field_key)
            assert offenders == [], offenders


class TestStatusRouting:
    """Submit should not require the user to know the intermediate statuses."""

    @pytest.mark.parametrize(
        "start",
        [
            CaseStatus.ASSIGNED,
            CaseStatus.ACCEPTED,
            CaseStatus.WIP,
            CaseStatus.FIELD_INVESTIGATION,
            CaseStatus.DOCUMENTS_PENDING,
            CaseStatus.RIP,
            CaseStatus.CORRECTION_REQUIRED,
        ],
    )
    def test_every_working_status_can_reach_submitted(self, start):
        route = path_to(start, CaseStatus.REPORT_SUBMITTED)
        assert route, f"no legal route from {start}"
        assert route[-1] == CaseStatus.REPORT_SUBMITTED

    def test_a_closed_case_has_no_route(self):
        assert path_to(CaseStatus.COMPLETED, CaseStatus.REPORT_SUBMITTED) == []

    def test_already_there_is_an_empty_route(self):
        assert path_to(CaseStatus.REPORT_SUBMITTED, CaseStatus.REPORT_SUBMITTED) == []


class TestFormFlow:
    async def _case_with_form(self, client: AsyncClient, headers, name: str) -> dict:
        templates = await client.get(f"{API}/form-templates", headers=headers)
        assert templates.status_code == 200, templates.text
        template = next(row for row in templates.json() if row["is_active"])

        created = await client.post(
            f"{API}/cases",
            json={
                "company_id": template["company_id"],
                "case_type_id": template["case_type_id"],
                "life_assured_name": name,
                "krn_no": f"KRN-{name.replace(' ', '')}",
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        case = created.json()

        me = await client.get(f"{API}/auth/me", headers=headers)
        assigned = await client.post(
            f"{API}/cases/{case['id']}/assign",
            json={"assigned_to_id": me.json()["id"]},
            headers=headers,
        )
        assert assigned.status_code == 200, assigned.text
        return case

    async def test_client_supplied_fields_are_editable(
        self, client: AsyncClient, admin_headers
    ):
        """No lock, no unlock request — a wrong policy number is just corrected."""
        case = await self._case_with_form(client, admin_headers, "Editable Subject")
        form = await client.get(
            f"{API}/cases/{case['id']}/form", headers=admin_headers
        )
        assert form.status_code == 200, form.text
        body = form.json()

        supplied = [
            field["field_key"]
            for section in body["template"]["sections"]
            for field in section["fields"]
            if field["source"] == "BANK_SUPPLIED" and not field["is_readonly"]
        ]
        if not supplied:
            pytest.skip("this template pre-fills nothing from the client file")

        saved = await client.put(
            f"{API}/cases/{case['id']}/form",
            json={"values": {supplied[0]: "Corrected on the visit"}, "submit": False},
            headers=admin_headers,
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["saved_fields"] == 1

    async def test_missing_required_fields_are_named_and_located(
        self, client: AsyncClient, admin_headers
    ):
        case = await self._case_with_form(client, admin_headers, "Incomplete Subject")
        form = await client.get(
            f"{API}/cases/{case['id']}/form", headers=admin_headers
        )
        body = form.json()

        # Set only the verdict, so the outcome guard passes and the required
        # check is what actually answers.
        outcome_key = next(
            (
                field["field_key"]
                for section in body["template"]["sections"]
                for field in section["fields"]
                if field.get("document_mapping") == "outcome"
            ),
            None,
        )
        assert outcome_key, "template has no verdict field"

        required = [
            field
            for section in body["template"]["sections"]
            for field in section["fields"]
            if field["is_required"] and field["field_key"] != outcome_key
        ]
        if not required:
            pytest.skip("this template has no other required fields")

        response = await client.put(
            f"{API}/cases/{case['id']}/form",
            json={"values": {outcome_key: "Positive"}, "submit": True},
            headers=admin_headers,
        )
        assert response.status_code == 422, response.text
        payload = response.json()["error"]

        missing = payload["details"]["missing"]
        assert missing, payload
        for entry in missing:
            assert entry["field_key"], entry
            assert entry["label"], entry
            assert entry["section"], entry
        # The message points at the first one rather than listing everything.
        assert missing[0]["label"] in payload["message"]

        # Nothing moved: a refused submit must not advance the case.
        detail = await client.get(
            f"{API}/cases/{case['id']}", headers=admin_headers
        )
        assert detail.json()["status"] != CaseStatus.REPORT_SUBMITTED.value

    async def test_submit_from_assigned_walks_the_route(
        self, client: AsyncClient, admin_headers
    ):
        case = await self._case_with_form(client, admin_headers, "Straight Through")
        form = await client.get(
            f"{API}/cases/{case['id']}/form", headers=admin_headers
        )
        body = form.json()
        assert body["can_edit"] is True

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

        # Assigning a case starts the work, so it is already in WIP here —
        # two legal steps short of Submitted rather than three.
        detail = await client.get(
            f"{API}/cases/{case['id']}", headers=admin_headers
        )
        assert detail.json()["status"] == CaseStatus.WIP.value

        submitted = await client.put(
            f"{API}/cases/{case['id']}/form",
            json={"values": values, "submit": True},
            headers=admin_headers,
        )
        assert submitted.status_code == 200, submitted.text

        detail = await client.get(
            f"{API}/cases/{case['id']}", headers=admin_headers
        )
        assert detail.json()["status"] == CaseStatus.REPORT_SUBMITTED.value

        # The intermediate steps are on the record, not skipped silently.
        history = await client.get(
            f"{API}/cases/{case['id']}/status-history", headers=admin_headers
        )
        moved = {row["new_status"] for row in history.json()}
        assert CaseStatus.WIP.value in moved
        assert CaseStatus.RIP.value in moved


class TestAttendanceAcrossSessions:
    """A second shift in one day must not blow up on mixed timestamps.

    SQLite returns naive datetimes while a row created in the same transaction
    still holds the timezone-aware value it was built with. Rolling the day up
    compared the two and raised, so the *second* clock-in of any day answered
    HTTP 500 — invisible to a test that only ever clocks in once.
    """

    async def test_two_shifts_in_one_day(self, client: AsyncClient, admin_headers):
        first = await client.post(
            f"{API}/attendance/clock-in", json={"note": "Morning"},
            headers=admin_headers,
        )
        assert first.status_code == 200, first.text
        assert first.json()["state"] == "CLOCKED_IN"

        out = await client.post(
            f"{API}/attendance/clock-out", json={}, headers=admin_headers
        )
        assert out.status_code == 200, out.text

        second = await client.post(
            f"{API}/attendance/clock-in", json={"note": "Afternoon"},
            headers=admin_headers,
        )
        assert second.status_code == 200, second.text
        body = second.json()
        assert body["state"] == "CLOCKED_IN"
        assert body["sessions_today"] == 2

        # And the header still reads a sane running total.
        status = await client.get(f"{API}/attendance/me", headers=admin_headers)
        assert status.status_code == 200, status.text
        assert status.json()["worked_display"].count(":") == 1

    async def test_timestamps_carry_a_timezone(
        self, client: AsyncClient, admin_headers
    ):
        """Naive ISO strings are read as local time by the browser."""
        await client.post(
            f"{API}/attendance/clock-in", json={}, headers=admin_headers
        )
        response = await client.get(f"{API}/attendance/me", headers=admin_headers)
        clock_in = response.json()["clock_in_at"]
        assert clock_in, response.text
        assert clock_in.endswith("Z") or "+" in clock_in[10:], clock_in
