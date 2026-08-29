"""A client's Status column must never create an unworkable case.

The daily file carries the *client's* own tracking status. Honouring it made
cases arrive Completed: read-only form, no way forward, and nothing in the UI
explaining why. Nobody importing today's work wants that.

So the file's status is kept as a note and the case starts on our side of the
workflow, unless the operator explicitly opts in for a historic load. And a
case closed by mistake can always be reopened, on the record.
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.config import settings
from app.models.enums import CaseOutcome, CaseStatus
from tests.test_workflow import IMPORT_HEADERS, build_workbook

API = settings.API_V1_PREFIX

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def import_row(name: str, krn: str, status: str) -> list[object]:
    """One valid row of the client's daily layout, with a chosen Status."""
    row = [
        "ICICI",            # Co. Name
        "Pre Issuance",     # Case Type
        "Aug-2026",         # Month
        "12-08-2026",       # Date
        2,                  # Aging
        krn,                # KRN No
        f"POL-{krn}",       # Policy Number
        "",                 # Application Number
        name,               # Life_Assured_Name
        "Lucknow",          # City
        "Uttar Pradesh",    # State
        "",                 # Assign To
        status,             # Status
        "",                 # Remark/ADD IO ID
        "226016",           # Pin Code
    ]
    assert len(row) == len(IMPORT_HEADERS), "row does not match the header set"
    return row


async def upload_and_commit(
    client: AsyncClient, headers, rows: list[list[object]], **options
) -> dict:
    upload = await client.post(
        f"{API}/imports/upload",
        files={"file": ("daily.xlsx", build_workbook(rows), XLSX)},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    preview = upload.json()

    commit = await client.post(
        f"{API}/imports/{preview['batch']['id']}/commit",
        json={"skip_duplicates": True, "auto_assign": True, **options},
        headers=headers,
    )
    assert commit.status_code == 200, commit.text
    return preview


async def find_case(client: AsyncClient, headers, name: str) -> dict:
    listing = await client.get(
        f"{API}/cases", params={"search": name}, headers=headers
    )
    assert listing.status_code == 200, listing.text
    rows = listing.json()["items"]
    assert len(rows) == 1, f"expected one case for {name}, got {rows}"
    return rows[0]


class TestImportedStatus:
    async def test_completed_in_the_file_still_creates_a_workable_case(
        self, client: AsyncClient, admin_headers
    ):
        name = "Status Column Subject"
        preview = await upload_and_commit(
            client, admin_headers, [import_row(name, "KRN-STATUS-1", "Completed")]
        )

        # The operator is told what will happen before they commit.
        warnings = [w for row in preview["rows"] for w in row.get("warnings", [])]
        assert any("kept as a note" in w for w in warnings), warnings

        case = await find_case(client, admin_headers, name)
        assert case["status"] != CaseStatus.COMPLETED.value
        assert case["status"] in {
            CaseStatus.IMPORTED.value,
            CaseStatus.UNASSIGNED.value,
        }

        detail = await client.get(
            f"{API}/cases/{case['id']}", headers=admin_headers
        )
        # The client's own wording survives as a note rather than being lost.
        assert "Completed" in (detail.json()["import_remark"] or "")

        form = await client.get(
            f"{API}/cases/{case['id']}/form", headers=admin_headers
        )
        assert form.status_code == 200, form.text
        assert form.json()["can_edit"] is True

    async def test_operator_can_opt_in_for_a_historic_load(
        self, client: AsyncClient, admin_headers
    ):
        """Loading closed historic records is real — it just is not the default."""
        name = "Historic Record Subject"
        await upload_and_commit(
            client,
            admin_headers,
            [import_row(name, "KRN-STATUS-2", "Completed")],
            apply_file_status=True,
        )
        case = await find_case(client, admin_headers, name)
        assert case["status"] == CaseStatus.COMPLETED.value


class TestReopen:
    """A closed case must have a way back, or the UI is a dead end."""

    async def _completed_case(self, client: AsyncClient, headers, name: str) -> str:
        templates = await client.get(f"{API}/form-templates", headers=headers)
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
        case_id = created.json()["id"]

        me = await client.get(f"{API}/auth/me", headers=headers)
        assigned = await client.post(
            f"{API}/cases/{case_id}/assign",
            json={"assigned_to_id": me.json()["id"]},
            headers=headers,
        )
        assert assigned.status_code == 200, assigned.text

        for target in (
            CaseStatus.WIP,
            CaseStatus.RIP,
            CaseStatus.REPORT_SUBMITTED,
            CaseStatus.UNDER_REVIEW,
            CaseStatus.VERIFIED,
            CaseStatus.COMPLETED,
        ):
            moved = await client.post(
                f"{API}/cases/{case_id}/status",
                json={
                    "status": target.value,
                    "outcome": CaseOutcome.POSITIVE.value,
                },
                headers=headers,
            )
            assert moved.status_code == 200, f"{target}: {moved.text}"
        return case_id

    async def test_reopen_returns_the_case_to_its_last_desk(
        self, client: AsyncClient, admin_headers
    ):
        case_id = await self._completed_case(
            client, admin_headers, "Reopen Subject"
        )

        form = await client.get(
            f"{API}/cases/{case_id}/form", headers=admin_headers
        )
        assert form.json()["can_edit"] is False

        reopened = await client.post(
            f"{API}/cases/{case_id}/reopen",
            json={"reason": "Closed in error by the imported file status."},
            headers=admin_headers,
        )
        assert reopened.status_code == 200, reopened.text

        detail = await client.get(
            f"{API}/cases/{case_id}", headers=admin_headers
        )
        payload = detail.json()
        assert payload["status"] == CaseStatus.ASSIGNED.value
        assert payload["completed_at"] is None

        form = await client.get(
            f"{API}/cases/{case_id}/form", headers=admin_headers
        )
        assert form.json()["can_edit"] is True

    async def test_reopen_demands_a_real_reason(
        self, client: AsyncClient, admin_headers
    ):
        case_id = await self._completed_case(
            client, admin_headers, "Reopen Reason Subject"
        )
        response = await client.post(
            f"{API}/cases/{case_id}/reopen",
            json={"reason": "no"},
            headers=admin_headers,
        )
        assert response.status_code == 422, response.text

    async def test_open_case_cannot_be_reopened(
        self, client: AsyncClient, admin_headers
    ):
        templates = await client.get(f"{API}/form-templates", headers=admin_headers)
        template = next(row for row in templates.json() if row["is_active"])
        created = await client.post(
            f"{API}/cases",
            json={
                "company_id": template["company_id"],
                "case_type_id": template["case_type_id"],
                "life_assured_name": "Already Open Subject",
                "krn_no": "KRN-REOPEN-OPEN",
            },
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text

        response = await client.post(
            f"{API}/cases/{created.json()['id']}/reopen",
            json={"reason": "There is nothing to reopen here."},
            headers=admin_headers,
        )
        assert response.status_code == 409, response.text
