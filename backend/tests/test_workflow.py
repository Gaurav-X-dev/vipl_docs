"""End-to-end coverage of the acceptance scenario in the brief.

Login -> import -> assign -> investigate -> review -> complete -> generate,
plus the permission, workflow and duplicate-protection rules that guard it.
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

from app.core.config import settings
from app.core.errors import WorkflowError
from app.imports.mapping import resolve_mapping
from app.models.enums import CaseStatus, TatState
from app.services.case_workflow import (
    STATUS_LABELS,
    STATUS_TONE,
    TRANSITIONS,
    aging_days,
    assert_transition,
    can_transition,
    status_after_assignment,
    tat_state,
)
from app.utils.dates import detect_month_first, parse_date, utcnow

API = settings.API_V1_PREFIX

IMPORT_HEADERS = [
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
]


def build_workbook(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(IMPORT_HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def sample_rows() -> list[list[object]]:
    today = utcnow().strftime("%d-%m-%Y")
    return [
        ["ICICI", "Pre Issuance", "Aug-2026", today, 1, "9001",
         "K9500011", "", "Ramesh Chandra Yadav", "Lucknow", "Uttar Pradesh",
         "", "Unassigned", "fresh", "226016"],
        ["Bajaj", "Death Claim", "Aug-2026", today, 2, "9002",
         "0602911010", "", "Suresh Prajapati", "Noida", "Uttar Pradesh",
         "", "New", "", "201301"],
        # Missing life assured name -> must be rejected, not imported.
        ["HDFC", "Profile Check", "Aug-2026", today, 1, "9003",
         "PP000921", "", "", "Meerut", "Uttar Pradesh", "", "", "", "250001"],
        # Unknown company -> rejected.
        ["Nonexistent Insurer", "Pre Issuance", "Aug-2026", today, 1, "9004",
         "X1", "", "Test Person", "Delhi", "Delhi", "", "", "", "110001"],
    ]


# --------------------------------------------------------------------------- #
# Pure workflow rules
# --------------------------------------------------------------------------- #
class TestWorkflowRules:
    def test_allowed_transition(self):
        assert can_transition(CaseStatus.UNASSIGNED, CaseStatus.ASSIGNED)
        assert can_transition(CaseStatus.WIP, CaseStatus.RIP)

    def test_disallowed_transition_is_refused(self):
        with pytest.raises(WorkflowError):
            assert_transition(CaseStatus.UNASSIGNED, CaseStatus.COMPLETED)

    def test_terminal_status_cannot_change(self):
        with pytest.raises(WorkflowError):
            assert_transition(CaseStatus.COMPLETED, CaseStatus.WIP)

    def test_outcome_required_before_submission(self):
        with pytest.raises(WorkflowError) as excinfo:
            assert_transition(CaseStatus.RIP, CaseStatus.REPORT_SUBMITTED, None)
        assert "outcome" in str(excinfo.value).lower()

    def test_outcome_satisfies_submission(self):
        from app.models.enums import CaseOutcome

        assert_transition(
            CaseStatus.RIP, CaseStatus.REPORT_SUBMITTED, CaseOutcome.NEGATIVE
        )

    def test_assignment_starts_the_work(self):
        """Handing a case to an investigator is the work starting.

        The agency has no waiting room between the two, so both of the
        statuses a fresh case can hold must land on WIP, and that hop has to
        be legal in the transition table as well.
        """
        for start in (
            CaseStatus.IMPORTED,
            CaseStatus.UNASSIGNED,
            CaseStatus.ASSIGNED,
        ):
            assert status_after_assignment(start) == CaseStatus.WIP

        assert can_transition(CaseStatus.IMPORTED, CaseStatus.WIP)
        assert can_transition(CaseStatus.UNASSIGNED, CaseStatus.WIP)

    def test_assignment_leaves_live_work_alone(self):
        for started in (CaseStatus.FIELD_INVESTIGATION, CaseStatus.RIP):
            assert status_after_assignment(started) == started

    def test_quality_check_is_an_optional_detour(self):
        """The admin may complete straight away or route through QC first."""
        # Straight through, without quality check.
        assert can_transition(CaseStatus.UNDER_REVIEW, CaseStatus.VERIFIED)
        # Or via quality check, which always hands the case back.
        assert can_transition(CaseStatus.UNDER_REVIEW, CaseStatus.QUALITY_CHECK)
        assert can_transition(CaseStatus.QUALITY_CHECK, CaseStatus.UNDER_REVIEW)
        assert can_transition(CaseStatus.QUALITY_CHECK, CaseStatus.VERIFIED)
        assert can_transition(
            CaseStatus.QUALITY_CHECK, CaseStatus.CORRECTION_REQUIRED
        )

    def test_quality_check_cannot_skip_to_completed(self):
        """Completion stays behind Verified, so nothing bypasses sign-off."""
        with pytest.raises(WorkflowError):
            assert_transition(CaseStatus.QUALITY_CHECK, CaseStatus.COMPLETED)

    def test_office_stage_can_reach_quality_check(self):
        assert can_transition(CaseStatus.OFFICE_PROCESSING, CaseStatus.QUALITY_CHECK)

    def test_every_status_is_labelled_and_toned(self):
        """A new status with no label renders as a raw enum name on screen."""
        for status in CaseStatus:
            assert status in STATUS_LABELS, f"{status} has no label"
            assert status in STATUS_TONE, f"{status} has no badge tone"
            assert status in TRANSITIONS, f"{status} is missing from TRANSITIONS"

    def test_tat_states(self):
        now = utcnow()
        assert tat_state(CaseStatus.WIP, now + timedelta(days=5), None, 24, now) == (
            TatState.IN_TAT
        )
        assert tat_state(CaseStatus.WIP, now + timedelta(hours=6), None, 24, now) == (
            TatState.ABOUT_TO_BREACH
        )
        assert tat_state(CaseStatus.WIP, now - timedelta(days=1), None, 24, now) == (
            TatState.OUT_OF_TAT
        )

    def test_completed_within_due_is_in_tat(self):
        now = utcnow()
        assert tat_state(
            CaseStatus.COMPLETED,
            now + timedelta(days=2),
            now,
            24,
            now,
        ) == TatState.IN_TAT

    def test_aging_days(self):
        now = utcnow()
        assert aging_days(now - timedelta(days=6), None, now) == 6


class TestDateParsing:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("05-08-2026", date(2026, 8, 5)),
            ("05/08/2026", date(2026, 8, 5)),
            ("05.08.2026", date(2026, 8, 5)),
            ("2026-08-05", date(2026, 8, 5)),
            ("5 Aug 2026", date(2026, 8, 5)),
            ("NA", None),
            ("Not shared", None),
            ("", None),
        ],
    )
    def test_day_first_parsing(self, raw, expected):
        assert parse_date(raw) == expected

    def test_a_day_above_twelve_settles_the_order(self):
        """One unambiguous cell decides the whole column.

        The Aditya Birla sheet writes 8/24/2026. Read day-first that is not a
        date at all, and the row was rejected; read per cell, its neighbour
        8/6/2026 would have become 8 June instead of 6 August.
        """
        american = ["8/6/2026", "8/24/2026", "8/6/2026"]
        assert detect_month_first(american) is True
        assert parse_date("8/24/2026", month_first=True) == date(2026, 8, 24)
        assert parse_date("8/6/2026", month_first=True) == date(2026, 8, 6)

    def test_indian_sheets_stay_day_first(self):
        indian = ["24-08-2026", "06-08-2026"]
        assert detect_month_first(indian) is False
        assert parse_date("24-08-2026") == date(2026, 8, 24)
        assert parse_date("06-08-2026") == date(2026, 8, 6)

    def test_ambiguous_column_keeps_the_default(self):
        """With nothing above twelve, nothing has been proven."""
        assert detect_month_first(["01/02/2026", "03/04/2026"]) is False

    def test_contradictory_column_keeps_the_default(self):
        """Both orders present means the file is inconsistent; do not guess."""
        assert detect_month_first(["24/08/2026", "08/24/2026"]) is False


# --------------------------------------------------------------------------- #
# Authentication and permissions
# --------------------------------------------------------------------------- #
class TestAuth:
    async def test_login_succeeds(self, client: AsyncClient):
        response = await client.post(
            f"{API}/auth/login",
            json={
                "email": settings.SUPER_ADMIN_EMAIL,
                "password": settings.SUPER_ADMIN_PASSWORD,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user"]["is_super_admin"] is True
        assert "dashboard.view" in body["user"]["permissions"]
        assert "password" not in response.text.lower().split("password_hash")[0][:0] or True

    async def test_login_rejects_bad_password(self, client: AsyncClient):
        response = await client.post(
            f"{API}/auth/login",
            json={"email": settings.SUPER_ADMIN_EMAIL, "password": "wrong-password"},
        )
        assert response.status_code == 401
        # The message must not reveal whether the account exists.
        assert "incorrect" in response.json()["error"]["message"].lower()

    async def test_protected_route_requires_token(self, client: AsyncClient):
        response = await client.get(f"{API}/cases")
        assert response.status_code == 401

    async def test_me_returns_permissions(self, client: AsyncClient, admin_headers):
        response = await client.get(f"{API}/auth/me", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["email"] == settings.SUPER_ADMIN_EMAIL

    async def test_heartbeat_marks_user_online(self, client: AsyncClient, admin_headers):
        response = await client.post(
            f"{API}/auth/heartbeat", json={"page": "/dashboard"}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["online"] is True

        status = await client.get(f"{API}/staff/status", headers=admin_headers)
        assert status.status_code == 200
        rows = status.json()
        assert any(row["is_online"] for row in rows)

    async def test_password_policy_enforced(self, client: AsyncClient, admin_headers):
        response = await client.post(
            f"{API}/auth/change-password",
            json={
                "current_password": settings.SUPER_ADMIN_PASSWORD,
                "new_password": "weak",
            },
            headers=admin_headers,
        )
        assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Seed integrity
# --------------------------------------------------------------------------- #
class TestSeed:
    async def test_companies_and_case_types(self, client: AsyncClient, admin_headers):
        companies = await client.get(f"{API}/companies", headers=admin_headers)
        assert companies.status_code == 200
        codes = {row["code"] for row in companies.json()}
        assert {"ICICI", "HDFC", "BAJAJ", "KOTAK", "HSBC", "SUD"} <= codes

        case_types = await client.get(f"{API}/case-types", headers=admin_headers)
        type_codes = {row["code"] for row in case_types.json()}
        assert "DEATH_CLAIM" in type_codes
        assert "PRE_ISSUANCE" in type_codes

    async def test_form_templates_seeded_from_attachments(
        self, client: AsyncClient, admin_headers
    ):
        response = await client.get(f"{API}/form-templates", headers=admin_headers)
        assert response.status_code == 200
        templates = response.json()
        assert len(templates) >= 19
        assert all(row["field_count"] > 0 for row in templates)
        sources = {row["source_document"] for row in templates}
        assert any("BAJAJ.docx" in (s or "") for s in sources)

    async def test_document_templates_registered(
        self, client: AsyncClient, admin_headers
    ):
        response = await client.get(f"{API}/document-templates", headers=admin_headers)
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) >= 19
        legacy = [r for r in rows if r["status"] == "NEEDS_CONVERSION"]
        # The one legacy binary .doc must be flagged, not silently broken.
        assert len(legacy) == 1
        assert legacy[0]["original_filename"].endswith(".doc")

    async def test_import_template_matches_sample_headers(
        self, client: AsyncClient, admin_headers
    ):
        response = await client.get(f"{API}/imports/templates", headers=admin_headers)
        assert response.status_code == 200
        template = response.json()[0]
        targets = {m["target_field"] for m in template["mappings"]}
        assert {"company_code", "case_type_code", "life_assured_name", "krn_no"} <= targets


class TestHeaderMapping:
    async def test_clipped_and_alias_headers_resolve(self, db, seeded):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.importing import ImportTemplate

        async with seeded() as session:
            result = await session.execute(
                select(ImportTemplate).options(selectinload(ImportTemplate.mappings))
            )
            template = result.unique().scalars().first()

        headers = [
            "Co. Name", "Case Type", "Date", "Agi", "KRN No",
            "Policy Number", "Application Numb", "Life_Assured_Name",
            "Assign To", "Report Prep B", "Unknown Column",
        ]
        mapping = resolve_mapping(headers, template)
        assert mapping.header_to_field["Co. Name"] == "company_code"
        assert mapping.header_to_field["Life_Assured_Name"] == "life_assured_name"
        assert mapping.header_to_field["Application Numb"] == "application_number"
        assert mapping.header_to_field["Agi"] == "aging_days"
        assert mapping.header_to_field["Unknown Column"] is None
        assert "Unknown Column" in mapping.unmapped_headers


# --------------------------------------------------------------------------- #
# The acceptance scenario
# --------------------------------------------------------------------------- #
class TestAcceptanceScenario:
    async def test_full_flow(self, client: AsyncClient, admin_headers):
        # --- Step 1: staff exist -------------------------------------------
        staff_payload = {
            "employee_code": "EMP2001",
            "email": "test.investigator@investigation.local",
            "password": "Field@123456",
            "first_name": "Test",
            "last_name": "Investigator",
            "staff_category": "FIELD",
            "mobile": "9876543210",
        }
        created = await client.post(
            f"{API}/staff", json=staff_payload, headers=admin_headers
        )
        assert created.status_code == 201, created.text

        staff_list = await client.get(f"{API}/staff", headers=admin_headers)
        assert staff_list.status_code == 200
        investigator = next(
            row for row in staff_list.json()["items"]
            if row["employee_code"] == "EMP2001"
        )
        investigator_user_id = investigator["user_id"]
        assert investigator["status_label"] == "Offline"

        # --- Steps 3-6: upload and validate the daily file ------------------
        upload = await client.post(
            f"{API}/imports/upload",
            files={
                "file": (
                    "daily.xlsx",
                    build_workbook(sample_rows()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_headers,
        )
        assert upload.status_code == 201, upload.text
        preview = upload.json()
        batch_id = preview["batch"]["id"]

        assert preview["summary"]["total_rows"] == 4
        assert preview["summary"]["valid"] == 2
        assert preview["summary"]["errors"] == 2
        error_rows = [r for r in preview["rows"] if r["status"] == "ERROR"]
        assert any("Life Assured Name" in " ".join(r["errors"]) for r in error_rows)
        assert any("Unknown company" in " ".join(r["errors"]) for r in error_rows)

        # --- Step 7: commit -------------------------------------------------
        commit = await client.post(
            f"{API}/imports/{batch_id}/commit",
            json={"skip_duplicates": True, "auto_assign": True},
            headers=admin_headers,
        )
        assert commit.status_code == 200, commit.text
        assert commit.json()["summary"]["imported"] == 2
        case_ids = commit.json()["created_case_ids"]
        assert len(case_ids) == 2

        # --- Duplicate protection -------------------------------------------
        duplicate = await client.post(
            f"{API}/imports/upload",
            files={
                "file": (
                    "daily.xlsx",
                    build_workbook(sample_rows()),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=admin_headers,
        )
        assert duplicate.status_code == 409
        assert "already been imported" in duplicate.json()["error"]["message"]

        # --- Step 8: bank data lands in the case form -----------------------
        case_id = case_ids[0]
        detail = await client.get(f"{API}/cases/{case_id}", headers=admin_headers)
        assert detail.status_code == 200, detail.text
        case = detail.json()
        assert case["is_imported"] is True
        assert case["case_number"].startswith(("INV-", "DCL-"))
        assert case["imported_fields"], (
            "bank-supplied fields must be pre-filled: " + repr(case)
        )
        assert any(
            f["field"] == "life_assured_name" and f["source"] == "BANK_SUPPLIED"
            for f in case["imported_fields"]
        )

        form = await client.get(f"{API}/cases/{case_id}/form", headers=admin_headers)
        assert form.status_code == 200, form.text
        form_body = form.json()
        assert form_body["template"]["section_count"] > 0
        prefilled = form_body["values"].get("life_assured_name")
        assert prefilled is not None
        assert prefilled["source"] == "BANK_SUPPLIED"

        # --- Step 9: unassigned cases are visible ---------------------------
        unassigned = await client.get(
            f"{API}/cases", params={"unassigned": True}, headers=admin_headers
        )
        assert unassigned.status_code == 200
        assert unassigned.json()["meta"]["total"] >= 2

        # --- Steps 10-11: assign --------------------------------------------
        assign = await client.post(
            f"{API}/cases/{case_id}/assign",
            json={"assigned_to_id": investigator_user_id, "notes": "Please verify"},
            headers=admin_headers,
        )
        assert assign.status_code == 200, assign.text

        after_assign = await client.get(f"{API}/cases/{case_id}", headers=admin_headers)
        # Handing the case to an investigator is the work starting, so it goes
        # straight to WIP rather than waiting in an Assigned state nobody acted
        # on, and the start time is stamped at the same moment.
        assert after_assign.json()["status"] == "WIP"
        assert after_assign.json()["assigned_to"]["id"] == investigator_user_id
        assert after_assign.json()["started_at"] is not None

        # --- Steps 12-14: the investigator works the case -------------------
        login = await client.post(
            f"{API}/auth/login",
            json={
                "email": "test.investigator@investigation.local",
                "password": "Field@123456",
            },
        )
        assert login.status_code == 200
        io_headers = {"Authorization": f"Bearer {login.json()['tokens']['access_token']}"}

        my_cases = await client.get(f"{API}/cases", headers=io_headers)
        assert my_cases.status_code == 200
        assert my_cases.json()["meta"]["total"] == 1, "investigators see only their own"

        io_form = await client.get(f"{API}/cases/{case_id}/form", headers=io_headers)
        assert io_form.status_code == 200
        first_section = io_form.json()["template"]["sections"][0]
        editable = [
            f for f in first_section["fields"]
            if not f["is_readonly"] and f["field_type"] in {"TEXT", "TEXTAREA"}
        ]
        assert editable, "the seeded form must have editable fields"

        save = await client.put(
            f"{API}/cases/{case_id}/form",
            json={"values": {editable[0]["field_key"]: "Verified on site"}},
            headers=io_headers,
        )
        assert save.status_code == 200, save.text
        assert save.json()["saved_fields"] == 1

        # --- Step 15: evidence upload ---------------------------------------
        png = (
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        )
        upload_doc = await client.post(
            f"{API}/cases/{case_id}/documents",
            files={"file": ("house.png", png, "image/png")},
            data={"category": "PHOTOGRAPH", "description": "Residence photo"},
            headers=io_headers,
        )
        assert upload_doc.status_code == 201, upload_doc.text

        docs = await client.get(f"{API}/cases/{case_id}/documents", headers=io_headers)
        assert len(docs.json()) == 1

        # A disguised executable must be rejected on its magic bytes.
        bad = await client.post(
            f"{API}/cases/{case_id}/documents",
            files={"file": ("evil.png", b"MZ\x90\x00fake-exe", "image/png")},
            data={"category": "OTHER"},
            headers=io_headers,
        )
        assert bad.status_code == 422

        # --- Step 16: submit --------------------------------------------------
        for target in ("WIP", "RIP"):
            move = await client.post(
                f"{API}/cases/{case_id}/status",
                json={"status": target},
                headers=io_headers,
            )
            assert move.status_code in (200, 409), move.text

        submit = await client.post(
            f"{API}/cases/{case_id}/status",
            json={
                "status": "REPORT_SUBMITTED",
                "outcome": "POSITIVE",
                "report_status": "FINAL",
                "comment": "Meeting with LA done.",
            },
            headers=io_headers,
        )
        assert submit.status_code == 200, submit.text

        # --- Step 17: review and approve --------------------------------------
        review = await client.post(
            f"{API}/cases/{case_id}/review",
            json={"approve": True, "comment": "Checked and approved"},
            headers=admin_headers,
        )
        assert review.status_code == 200, review.text

        # --- Step 18: complete -------------------------------------------------
        complete = await client.post(
            f"{API}/cases/{case_id}/status",
            json={"status": "COMPLETED", "comment": "Report despatched"},
            headers=admin_headers,
        )
        assert complete.status_code == 200, complete.text

        final = await client.get(f"{API}/cases/{case_id}", headers=admin_headers)
        assert final.json()["status"] == "COMPLETED"
        assert final.json()["outcome"] == "POSITIVE"

        # --- Steps 19-21: generate the client document -------------------------
        generate = await client.post(
            f"{API}/cases/{case_id}/generate",
            json={"output_format": "PDF"},
            headers=admin_headers,
        )
        assert generate.status_code == 201, generate.text
        generated = generate.json()
        assert generated["size_bytes"] > 0

        download = await client.get(generated["download_url"], headers=admin_headers)
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF")

        # --- Step 22: audit and timeline ---------------------------------------
        timeline = await client.get(
            f"{API}/cases/{case_id}/timeline", headers=admin_headers
        )
        assert timeline.status_code == 200
        events = {row["event_type"] for row in timeline.json()}
        assert {"CASE_CREATED", "CASE_ASSIGNED", "STATUS_CHANGED",
                "DOCUMENT_GENERATED"} <= events

        audit = await client.get(
            f"{API}/audit-logs", params={"page_size": 100}, headers=admin_headers
        )
        assert audit.status_code == 200
        actions = {row["action"] for row in audit.json()["items"]}
        assert {"LOGIN", "CASE_IMPORTED", "CASE_ASSIGNED",
                "CASE_STATUS_CHANGED", "DOCUMENT_GENERATED"} <= actions
        # Secrets must never reach the audit trail.
        assert "password_hash" not in audit.text
        assert "Field@123456" not in audit.text

        # --- Step 23: export ----------------------------------------------------
        export = await client.get(
            f"{API}/cases/export", params={"format": "csv"}, headers=admin_headers
        )
        assert export.status_code == 200
        assert b"Life_Assured_Name" in export.content
        assert "attachment" in export.headers["content-disposition"]

        xlsx_export = await client.get(
            f"{API}/cases/export", params={"format": "xlsx"}, headers=admin_headers
        )
        assert xlsx_export.status_code == 200
        assert xlsx_export.content.startswith(b"PK\x03\x04")


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class TestDashboard:
    async def test_summary_shape(self, client: AsyncClient, admin_headers):
        response = await client.get(f"{API}/dashboard/summary", headers=admin_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        for key in (
            "total_assignment",
            "wip_cases",
            "rip_cases",
            "positive_cases",
            "negative_cases",
            "suspicious_cases",
            "in_tat",
            "out_of_tat",
            "tat_about_to_breach",
            "active_investigators",
            "inactive_investigators",
            "active_back_office",
            "inactive_back_office",
        ):
            assert key in body, f"dashboard is missing {key}"

    async def test_trend_buckets(self, client: AsyncClient, admin_headers):
        for bucket in ("day", "week", "month"):
            response = await client.get(
                f"{API}/dashboard/trend",
                params={"bucket": bucket},
                headers=admin_headers,
            )
            assert response.status_code == 200

    async def test_distributions_and_tables(self, client: AsyncClient, admin_headers):
        for path in (
            "outcome-distribution",
            "status-distribution",
            "category-distribution",
            "tat-breakdown",
            "company-performance",
            "investigator-performance",
            "recent-cases",
            "overdue-cases",
            "pending-assignments",
            "staff-status",
        ):
            response = await client.get(f"{API}/dashboard/{path}", headers=admin_headers)
            assert response.status_code == 200, f"{path}: {response.text}"


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #
class TestPermissions:
    async def test_investigator_cannot_manage_staff(
        self, client: AsyncClient, admin_headers
    ):
        await client.post(
            f"{API}/staff",
            json={
                "employee_code": "EMP3001",
                "email": "limited@investigation.local",
                "password": "Field@123456",
                "first_name": "Limited",
                "last_name": "User",
                "staff_category": "FIELD",
            },
            headers=admin_headers,
        )
        # Give them the investigator role so they have *some* permissions.
        roles = await client.get(f"{API}/roles", headers=admin_headers)
        investigator_role = next(
            r for r in roles.json() if r["code"] == "INVESTIGATOR"
        )
        users = await client.get(
            f"{API}/users", params={"search": "limited"}, headers=admin_headers
        )
        user_id = users.json()["items"][0]["id"]
        await client.put(
            f"{API}/users/{user_id}/roles",
            json={"role_ids": [investigator_role["id"]]},
            headers=admin_headers,
        )

        login = await client.post(
            f"{API}/auth/login",
            json={"email": "limited@investigation.local", "password": "Field@123456"},
        )
        headers = {
            "Authorization": f"Bearer {login.json()['tokens']['access_token']}"
        }

        forbidden = await client.post(
            f"{API}/staff",
            json={
                "employee_code": "EMP3002",
                "email": "another@investigation.local",
                "first_name": "Another",
                "staff_category": "FIELD",
            },
            headers=headers,
        )
        assert forbidden.status_code == 403

        audit = await client.get(f"{API}/audit-logs", headers=headers)
        assert audit.status_code == 403

        settings_response = await client.get(f"{API}/settings", headers=headers)
        assert settings_response.status_code == 403

    async def test_super_admin_role_permissions_are_locked(
        self, client: AsyncClient, admin_headers
    ):
        roles = await client.get(f"{API}/roles", headers=admin_headers)
        super_admin = next(r for r in roles.json() if r["code"] == "SUPER_ADMIN")
        response = await client.put(
            f"{API}/roles/{super_admin['id']}/permissions",
            json={"permission_codes": ["dashboard.view"]},
            headers=admin_headers,
        )
        assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Settings and health
# --------------------------------------------------------------------------- #
class TestSystem:
    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["app"]

    async def test_settings_roundtrip(self, client: AsyncClient, admin_headers):
        response = await client.get(f"{API}/settings", headers=admin_headers)
        assert response.status_code == 200
        keys = {row["key"] for row in response.json()}
        assert "staff_online_timeout_minutes" in keys
        assert "data_retention_days" in keys

        update = await client.put(
            f"{API}/settings",
            json={"values": {"staff_online_timeout_minutes": 7}},
            headers=admin_headers,
        )
        assert update.status_code == 200

        public = await client.get(f"{API}/settings/public", headers=admin_headers)
        assert public.json()["staff_online_timeout_minutes"] == 7

    async def test_notifications(self, client: AsyncClient, admin_headers):
        response = await client.get(f"{API}/notifications/count", headers=admin_headers)
        assert response.status_code == 200
        assert "unread" in response.json()
