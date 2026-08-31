"""The client's own daily sheet, imported exactly as supplied.

This is a real Aditya Birla file, kept verbatim — the same header row, the same
three case-type labels, the same trailing empty columns and the double spaces
in the names. Synthetic fixtures had been passing while this file would not
import, because it uses wording that existed nowhere in the seed.

It also pins the queue split: an investigation sheet uploaded to the death
claim screen must be reported, not filed in the wrong place.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import settings

API = settings.API_V1_PREFIX

CSV_UPLOAD = "text/csv"

#: Verbatim from the client, including the columns their sheet carries beyond
#: the ones the importer needs.
CLIENT_SHEET = """Co. Name,Case Type,Month,Date,Aging,KRN No,Policy Number,Application Number,Life_Assured_Name,City,State,Assign To,Status,Remark/ADD IO ID,Pin Code,Report,Completion Date,Report Prep By
Aditya Birla,Project Verification,August,8/6/2026,23,,10434003,LA54779644,MR. GUDDU  MAURYA,Hardoi,Uttar Pradesh,,,,241304,,,
Aditya Birla,Project Verification,August,8/6/2026,23,,10400231,LA54735706,MR. AMRESH  BAHADUR,Jaunpur,Uttar Pradesh,,,,222143,,,
Aditya Birla,Project Verification,August,8/6/2026,23,,10395635,LA54726872,MR. MANOJ KUMAR SINGH,Chandauli,Uttar Pradesh,,,,232106,,,
Aditya Birla,Project Verification,August,8/6/2026,23,,10405558,LA54741001,MR. ARVIND KUMAR JAYASAWAL,Jaunpur,Uttar Pradesh,,,,222165,,,
Aditya Birla,Project Verification,August,8/6/2026,23,,10400636,LA54736694,MR. RAZZAB  ALI,Chandauli,Uttar Pradesh,,,,232111,,,
Aditya Birla,Project Verification,August,8/6/2026,23,,10394464,LA54725634,MRS. SARITA,Jaunpur,Uttar Pradesh,,,,222201,,,
Aditya Birla,Project Verification,August,8/6/2026,23,,10393582,LA54725835,MR. SANJAY  KUMAR,Jaunpur,Uttar Pradesh,,,,222201,,,
Aditya Birla,Physical Verification,August,8/24/2026,5,,10464164,LA54781224,MR. RAHUL  SONKAR,Balrampur,Uttar Pradesh,,,,271201,,,
Aditya Birla,Physical Verification,August,8/24/2026,5,,10465657,LA54822371,MS RAMKALI  .,Kheri,Uttar Pradesh,,,,261505,,,
Aditya Birla,Physical Verification,August,8/24/2026,5,,10445128,LA54800063,MR. ANKIT KUMAR PANCHAL,Muzaffarnagar,Uttar Pradesh,,,,247777,,,
Aditya Birla,Post Verification,August,8/24/2026,5,,10451139,LA54809229,MR. BABLU,Sant Kabeer Nagar,Uttar Pradesh,,,,272162,,,
Aditya Birla,Post Verification,August,8/24/2026,5,,10442786,LM00083030,MS PRIYAL,Kaushambi,Uttar Pradesh,,,,212201,,,
Aditya Birla,Post Verification,August,8/24/2026,5,,10456974,LA54815622,MRS. SONI,Kannauj,Uttar Pradesh,,,,209732,,,
"""

ROW_COUNT = 13


def sheet_bytes(body: str = CLIENT_SHEET) -> bytes:
    return body.encode("utf-8")


async def upload(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    body: str = CLIENT_SHEET,
    category: str | None = None,
    filename: str = "aditya-birla-daily.csv",
):
    data = {"category": category} if category else None
    return await client.post(
        f"{API}/imports/upload",
        files={"file": (filename, sheet_bytes(body), CSV_UPLOAD)},
        data=data,
        headers=headers,
    )


@pytest.mark.anyio
class TestClientSheet:
    async def test_every_row_is_accepted(self, client: AsyncClient, admin_headers):
        """No row may fail. A rejected row is a case nobody investigates."""
        response = await upload(client, admin_headers)
        assert response.status_code == 201, response.text

        summary = response.json()["summary"]
        assert summary["total_rows"] == ROW_COUNT
        assert summary["errors"] == 0, _first_errors(response.json())
        assert summary["valid"] == ROW_COUNT

    async def test_the_three_labels_route_to_one_form(
        self, client: AsyncClient, admin_headers
    ):
        """Project, Physical and Post Verification are one Aditya Birla form."""
        response = await upload(client, admin_headers)
        rows = response.json()["rows"]

        companies = {row["parsed"]["company_code"] for row in rows}
        assert companies == {"Aditya Birla"}

        labels = {row["parsed"]["case_type_code"] for row in rows}
        assert labels == {
            "Project Verification",
            "Physical Verification",
            "Post Verification",
        }, "the sheet's own wording must survive into the imported data"

    async def test_commit_creates_every_case(self, client: AsyncClient, admin_headers):
        response = await upload(client, admin_headers)
        batch_id = response.json()["batch"]["id"]

        commit = await client.post(
            f"{API}/imports/{batch_id}/commit",
            json={"skip_duplicates": True, "auto_assign": False},
            headers=admin_headers,
        )
        assert commit.status_code == 200, commit.text
        assert commit.json()["summary"]["imported"] == ROW_COUNT

        created = commit.json()["created_case_ids"]
        assert len(created) == ROW_COUNT

        detail = await client.get(f"{API}/cases/{created[0]}", headers=admin_headers)
        assert detail.status_code == 200
        case = detail.json()
        assert case["company_name"].startswith("Aditya Birla")
        assert case["category"] == "INVESTIGATION"
        # All three sheet labels are one form, so every case lands on it.
        assert case["case_type_code"] == "PRE_ISSUANCE"

    async def test_investigation_sheet_is_refused_by_the_death_claim_screen(
        self, client: AsyncClient, admin_headers
    ):
        """The queue split: the wrong screen reports rather than misfiles."""
        response = await upload(client, admin_headers, category="DEATH_CLAIM")
        assert response.status_code == 201, response.text

        summary = response.json()["summary"]
        assert summary["errors"] == ROW_COUNT
        assert summary["valid"] == 0

        message = " ".join(_first_errors(response.json()))
        assert "Investigation" in message
        assert "screen" in message

    async def test_the_same_sheet_still_imports_from_its_own_screen(
        self, client: AsyncClient, admin_headers
    ):
        response = await upload(client, admin_headers, category="INVESTIGATION")
        assert response.status_code == 201, response.text
        assert response.json()["summary"]["valid"] == ROW_COUNT


def _first_errors(preview: dict, limit: int = 3) -> list[str]:
    messages: list[str] = []
    for row in preview.get("rows", []):
        for problem in row.get("errors") or []:
            messages.append(f"row {row.get('row_number')}: {problem}")
            if len(messages) >= limit:
                return messages
    return messages
