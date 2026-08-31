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


# --------------------------------------------------------------------------- #
# The master pendency sheets
# --------------------------------------------------------------------------- #
#: Every company/case-type pair in the two master sheets the agency actually
#: works from, with the number of rows each accounted for. 158 of 350 rows in
#: the new-business sheet were rejected because five of these labels existed
#: nowhere in the seed, so they are pinned here rather than left to be
#: rediscovered by a client.
NEW_BUSINESS_PAIRS = [
    ("Aditya Birla", "Physical Verification", "PRE_ISSUANCE", 23),
    ("Aditya Birla", "Post Verification", "PRE_ISSUANCE", 55),
    ("Aditya Birla", "Project Verification", "PRE_ISSUANCE", 4),
    ("BXA", "Pre Claim", "PRE_CLAIM", 27),
    ("Bajaj", "Pre Issuance", "PRE_ISSUANCE", 24),
    ("Bandhan", "Post Issuance", "PRE_ISSUANCE", 14),
    ("Bandhan", "Pre Issuance", "PRE_ISSUANCE", 1),
    ("HDFC", "Profile Check", "PROFILE_CHECK", 41),
    ("HSBC", "Post Issuance", "PRE_ISSUANCE", 3),
    ("HSBC", "Pre Issuance", "PRE_ISSUANCE", 3),
    ("ICICI", "ADD", "PROFILE_CHECK", 35),
    ("ICICI", "Discreet Check", "DISCREET_CHECK", 1),
    ("ICICI", "Payout", "PAYOUT_VERIFICATION", 5),
    ("ICICI", "Policy Assignment", "PAYOUT_VERIFICATION", 1),
    ("Kotak", "PIPV", "PRE_CLAIM", 11),
    ("PNB", "Retail", "PRE_CLAIM", 102),
]

DEATH_CLAIM_PAIRS = [
    ("Bajaj", "Claim", 6),
    ("Bajaj", "DC Verification", 2),
    ("Bandhan", "Claim", 1),
    ("HDFC", "Claim", 21),
    ("HDFC", "Document Procurement", 2),
    ("ICICI", "Claim", 8),
    ("ICICI", "Document Procurement", 1),
    ("ICICI", "Health Claim", 2),
    ("ICICI", "PMJJY", 2),
    ("Kotak", "Claim", 37),
    ("Kotak", "Document Procurement", 1),
    ("Kotak", "Runner Boy", 4),
    ("SUD Life", "Claim", 3),
    ("SUD Life", "DC Verification", 2),
    ("SUD Life", "PMJJY", 3),
]


@pytest.mark.anyio
class TestMasterSheetVocabulary:
    """Every word the two master sheets use must resolve to a form."""

    async def _cache(self, seeded):
        from app.services.import_service import ResolverCache

        async with seeded() as session:
            cache = ResolverCache()
            await cache.load(session)
            return cache

    async def test_new_business_sheet_resolves_completely(self, db, seeded):
        cache = await self._cache(seeded)
        unresolved: list[str] = []
        for company_label, type_label, expected_code, rows in NEW_BUSINESS_PAIRS:
            company = cache.company(company_label)
            if company is None:
                unresolved.append(f"{rows} rows: company '{company_label}'")
                continue
            case_type = cache.case_type(type_label, company)
            if case_type is None:
                unresolved.append(
                    f"{rows} rows: case type '{type_label}' for {company.short_name}"
                )
                continue
            assert case_type.code == expected_code, (
                f"'{type_label}' for {company.short_name} went to "
                f"{case_type.code}, expected {expected_code}"
            )
        assert unresolved == [], unresolved

    async def test_death_claim_sheet_resolves_completely(self, db, seeded):
        cache = await self._cache(seeded)
        unresolved: list[str] = []
        for company_label, type_label, rows in DEATH_CLAIM_PAIRS:
            company = cache.company(company_label)
            if company is None:
                unresolved.append(f"{rows} rows: company '{company_label}'")
                continue
            case_type = cache.case_type(type_label, company)
            if case_type is None:
                unresolved.append(
                    f"{rows} rows: case type '{type_label}' for {company.short_name}"
                )
                continue
            assert case_type.category.value == "DEATH_CLAIM", (
                f"'{type_label}' for {company.short_name} is filed as "
                f"{case_type.category.value}"
            )
        assert unresolved == [], unresolved

    async def test_company_scoped_wording_stays_scoped(self, db, seeded):
        """"Retail" means something to PNB. It must not leak to everyone."""
        cache = await self._cache(seeded)
        pnb = cache.company("PNB")
        hdfc = cache.company("HDFC")
        assert cache.case_type("Retail", pnb) is not None
        assert cache.case_type("Retail", hdfc) is None
        assert cache.case_type("Retail", None) is None

        kotak = cache.company("Kotak")
        assert cache.case_type("Runner Boy", kotak) is not None
        assert cache.case_type("Runner Boy", hdfc) is None


@pytest.mark.anyio
class TestRollbackAfterAssignment:
    """Assigning a case must not make its batch unrollbackable.

    Importing with auto-assign now puts cases straight into Work in Progress.
    A rollback rule that read the status alone then refused every fresh batch —
    "work has already started" on cases nobody had touched.
    """

    async def _committed_batch(self, client: AsyncClient, headers):
        response = await upload(client, headers, category="INVESTIGATION")
        batch_id = response.json()["batch"]["id"]
        commit = await client.post(
            f"{API}/imports/{batch_id}/commit",
            json={"skip_duplicates": True, "auto_assign": False},
            headers=headers,
        )
        assert commit.status_code == 200, commit.text
        return batch_id, commit.json()["created_case_ids"]

    async def test_an_assigned_but_untouched_batch_rolls_back(
        self, client: AsyncClient, admin_headers
    ):
        batch_id, case_ids = await self._committed_batch(client, admin_headers)
        me = await client.get(f"{API}/auth/me", headers=admin_headers)

        assigned = await client.post(
            f"{API}/cases/{case_ids[0]}/assign",
            json={"assigned_to_id": me.json()["id"]},
            headers=admin_headers,
        )
        assert assigned.status_code == 200, assigned.text

        detail = await client.get(f"{API}/cases/{case_ids[0]}", headers=admin_headers)
        assert detail.json()["status"] == "WIP", "assignment should start the work"

        rolled = await client.post(
            f"{API}/imports/{batch_id}/rollback", headers=admin_headers
        )
        assert rolled.status_code == 200, rolled.text

        gone = await client.get(f"{API}/cases/{case_ids[0]}", headers=admin_headers)
        assert gone.status_code == 404

    async def test_a_prefilled_assignee_is_not_somebody_else_s_work(
        self, client: AsyncClient, admin_headers
    ):
        """The case that actually broke on the live server.

        When the sheet names an assignee, templates prefill fields such as
        "Field Executive Name" from it — and those fields declare their source
        as INVESTIGATION, not BANK_SUPPLIED. Filtering on the source therefore
        counted the import's own values as staff work, and the 24 rows whose
        Assign To column was filled blocked the whole batch from being rolled
        back.
        """
        me = await client.get(f"{API}/auth/me", headers=admin_headers)
        assignee = me.json()["email"]

        # Put that assignee into every row, which is what the master sheet does.
        lines = CLIENT_SHEET.strip().splitlines()
        header, body = lines[0], lines[1:]
        column = header.split(",").index("Assign To")
        rows = []
        for line in body:
            cells = line.split(",")
            cells[column] = assignee
            rows.append(",".join(cells))
        sheet = "\n".join([header, *rows]) + "\n"

        response = await upload(client, admin_headers, body=sheet, category="INVESTIGATION")
        assert response.status_code == 201, response.text
        batch_id = response.json()["batch"]["id"]

        commit = await client.post(
            f"{API}/imports/{batch_id}/commit",
            json={"skip_duplicates": True, "auto_assign": True},
            headers=admin_headers,
        )
        assert commit.status_code == 200, commit.text
        created = commit.json()["created_case_ids"]
        assert created, "the sheet should have produced cases"

        rolled = await client.post(
            f"{API}/imports/{batch_id}/rollback", headers=admin_headers
        )
        assert rolled.status_code == 200, rolled.text

        gone = await client.get(f"{API}/cases/{created[0]}", headers=admin_headers)
        assert gone.status_code == 404

    async def test_a_batch_with_real_work_still_refuses(
        self, client: AsyncClient, admin_headers
    ):
        batch_id, case_ids = await self._committed_batch(client, admin_headers)
        case_id = case_ids[0]

        # A note is the cheapest thing a person can leave behind.
        note = await client.post(
            f"{API}/cases/{case_id}/notes",
            json={"body": "Spoke to the neighbour.", "is_internal": True},
            headers=admin_headers,
        )
        assert note.status_code == 201, note.text

        refused = await client.post(
            f"{API}/imports/{batch_id}/rollback", headers=admin_headers
        )
        assert refused.status_code == 409, refused.text
        assert "work has already started" in refused.text
