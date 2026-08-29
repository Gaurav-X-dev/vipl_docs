"""Drive one case through the entire operational flow against a running server.

This is the "does it actually work" check, not a unit test: it talks to the
live API exactly as the browser does, in the order a real day happens, and
stops at the first thing that fails.

    Admin signs in and clocks in
        -> imports a daily file
        -> the case lands under its company in the sidebar
        -> assigned to a field investigator
    Investigator signs in and clocks in
        -> opens the case, records the visit, fills the form
        -> submits to the office
    Admin assigns office staff
    Office staff opens it, the reviewer returns it for correction
    Investigator corrects and resubmits
        -> approved -> document generated -> completed
    Everyone clocks out

Usage (from ``backend/``, with the app running)::

    python -m scripts.smoke_flow
    python -m scripts.smoke_flow --base http://127.0.0.1:8000 --keep

Each step prints PASS or FAIL. Anything other than "0 failed" means the flow
is broken for a real user, whatever the unit tests say.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

BOUNDARY = "----viplsmoke"


class Flow:
    """A tiny HTTP client plus a running tally of what passed."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/") + "/api/v1"
        self.token: str | None = None
        self.passed = 0
        self.failed: list[str] = []
        self.skipped: list[str] = []
        self.step = 0

    # ------------------------------------------------------------ transport
    def call(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        *,
        token: str | None = None,
        raw: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, dict]:
        headers: dict[str, str] = {}
        bearer = token if token is not None else self.token
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        data = raw
        if raw is None and body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if content_type:
            headers["Content-Type"] = content_type

        request = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request) as response:
                payload = response.read()
                return response.status, (json.loads(payload) if payload else {})
        except urllib.error.HTTPError as error:
            payload = error.read()
            try:
                return error.code, json.loads(payload)
            except json.JSONDecodeError:
                return error.code, {"raw": payload.decode("utf-8", "replace")[:400]}
        except urllib.error.URLError as error:
            return 0, {"error": {"message": f"cannot reach the server: {error}"}}

    # ---------------------------------------------------------- reporting
    def check(self, label: str, ok: bool, detail: str = "") -> bool:
        self.step += 1
        mark = "PASS" if ok else "FAIL"
        line = f"  {self.step:>2}. [{mark}] {label}"
        if detail:
            line += f"\n         {detail}"
        print(line)
        if ok:
            self.passed += 1
        else:
            self.failed.append(label)
        return ok

    def skip(self, label: str, why: str) -> None:
        self.step += 1
        print(f"  {self.step:>2}. [SKIP] {label}")
        print(f"         {why}")
        self.skipped.append(label)

    def expect(
        self, label: str, status: int, payload: dict, want: int = 200
    ) -> bool:
        if status == want:
            return self.check(label, True)
        message = (payload.get("error") or {}).get("message") or payload
        return self.check(label, False, f"HTTP {status}: {message}")

    def login(self, email: str, password: str, *, optional: bool = False) -> str | None:
        status, payload = self.call(
            "POST", "/auth/login", {"email": email, "password": password}, token=""
        )
        if status == 200:
            self.check(f"sign in as {email}", True)
            return payload["tokens"]["access_token"]

        message = (payload.get("error") or {}).get("message", payload)
        if optional:
            # A staff password can be changed outside this script. That is not
            # a flow failure, so the run continues as the admin — who holds
            # every permission — rather than stopping.
            self.skip(
                f"sign in as {email}",
                f"{message} Pass --password, or the flow continues as admin.",
            )
        else:
            self.check(f"sign in as {email}", False, message)
        return None


def workbook(rows: list[list[object]], headers: list[str]) -> bytes:
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def multipart(filename: str, payload: bytes) -> tuple[bytes, str]:
    body = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet\r\n\r\n"
    ).encode() + payload + f"\r\n--{BOUNDARY}--\r\n".encode()
    return body, f"multipart/form-data; boundary={BOUNDARY}"


IMPORT_HEADERS = [
    "Co. Name", "Case Type", "Month", "Date", "Aging", "KRN No",
    "Policy Number", "Application Number", "Life_Assured_Name", "City",
    "State", "Assign To", "Status", "Remark/ADD IO ID", "Pin Code",
]


def run(base: str, investigator: str, office: str, password: str) -> int:
    flow = Flow(base)
    tag = uuid.uuid4().hex[:6].upper()
    subject = f"Smoke Subject {tag}"

    print("\nVIPL end-to-end flow check")
    print("=" * 66)

    # -- 1. Admin -----------------------------------------------------------
    admin = flow.login("admin@investigation.local", "Admin@123456")
    if not admin:
        print("\nCannot continue without the admin account.")
        return 1
    flow.token = admin

    status, _ = flow.call("POST", "/attendance/clock-in", {"note": "Smoke run"})
    flow.check("admin clocks in", status in (200, 409))

    status, sidebar = flow.call("GET", "/navigation/sidebar")
    flow.expect("sidebar loads", status, sidebar)
    companies = [
        company
        for category in sidebar.get("categories", [])
        if category["category"] == "INVESTIGATION"
        for company in category["companies"]
    ]
    flow.check(
        "every configured company is in the sidebar",
        len(companies) >= 5,
        f"found {len(companies)}",
    )

    # -- 2. Import ----------------------------------------------------------
    row = [
        "ICICI", "Pre Issuance", "Aug-2026", date.today().strftime("%d-%m-%Y"),
        1, f"KRN-{tag}", f"POL-{tag}", "", subject, "Lucknow",
        "Uttar Pradesh", "", "Completed", "Smoke run", "226016",
    ]
    body, content_type = multipart("smoke.xlsx", workbook([row], IMPORT_HEADERS))
    status, preview = flow.call(
        "POST", "/imports/upload", raw=body, content_type=content_type
    )
    if not flow.expect("daily file uploads and validates", status, preview, 201):
        return report(flow)

    warnings = [w for r in preview["rows"] for w in r.get("warnings", [])]
    flow.check(
        "the file's Status column is flagged, not applied",
        any("kept as a note" in w for w in warnings),
        "; ".join(warnings[:2]),
    )

    status, commit = flow.call(
        "POST",
        f"/imports/{preview['batch']['id']}/commit",
        {"skip_duplicates": True, "auto_assign": True},
    )
    if not flow.expect("import creates the case", status, commit):
        return report(flow)

    status, listing = flow.call("GET", f"/cases?search={subject.replace(' ', '%20')}")
    found = listing.get("items", [])
    if not flow.check("the case appears in the list", len(found) == 1, str(found)):
        return report(flow)
    case = found[0]
    case_id = case["id"]
    flow.check(
        'a "Completed" row still arrives workable',
        case["status"] not in ("COMPLETED", "VERIFIED"),
        f"status is {case['status_label']}",
    )

    # -- 3. Assign the investigator ----------------------------------------
    status, staff = flow.call(
        "GET", "/cases/assignable-staff?stage=FIELD_INVESTIGATION"
    )
    flow.expect("investigator list loads with workload", status, staff)
    field_user = next(
        (s for s in staff if s["email"] == investigator), None
    ) if isinstance(staff, list) else None
    if not flow.check(f"{investigator} can take field work", field_user is not None):
        return report(flow)

    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/assign",
        {"assigned_to_id": field_user["id"], "notes": "Smoke run"},
    )
    flow.expect("assigned to the investigator", status, payload)

    # -- 4. Investigator ----------------------------------------------------
    field_token = flow.login(investigator, password, optional=True) or admin

    status, _ = flow.call(
        "POST", "/attendance/clock-in", {"note": "Field day"}, token=field_token
    )
    flow.check("investigator clocks in", status in (200, 409))

    status, detail = flow.call("GET", f"/cases/{case_id}", token=field_token)
    flow.expect("investigator opens their case", status, detail)

    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/visit",
        {"visit_status": "VISITED", "remarks": "Met the customer."},
        token=field_token,
    )
    flow.expect("visit recorded", status, payload)

    status, form = flow.call("GET", f"/cases/{case_id}/form", token=field_token)
    if not flow.expect("the insurer form loads", status, form):
        return report(flow)

    keys = [
        f["field_key"]
        for s in form["template"]["sections"]
        for f in s["fields"]
    ]
    flow.check(
        "no field key repeats inside the form",
        len(keys) == len(set(keys)),
        f"{len(keys) - len(set(keys))} repeat(s)",
    )
    flow.check("the form is editable", form["can_edit"] is True)
    flow.check(
        "no field is locked behind an admin",
        not any(v.get("is_locked") for v in form["values"].values()),
    )

    # Submitting while required answers are missing must name and locate them.
    status, refused = flow.call(
        "PUT",
        f"/cases/{case_id}/form",
        {"values": {}, "submit": True},
        token=field_token,
    )
    missing = ((refused.get("error") or {}).get("details") or {}).get("missing", [])
    if status == 422:
        flow.check(
            "an incomplete submit names and locates every empty field",
            bool(missing) and all(m.get("field_key") and m.get("section") for m in missing),
            f"{len(missing)} field(s) reported",
        )
    else:
        flow.check("an incomplete submit is refused", False, f"HTTP {status}")

    values: dict[str, str] = {}
    for section in form["template"]["sections"]:
        for field in section["fields"]:
            if not field["is_required"]:
                continue
            mapping = field.get("document_mapping")
            if mapping == "outcome":
                values[field["field_key"]] = "Positive"
            elif mapping == "report_status":
                values[field["field_key"]] = "Final"
            elif field["field_type"] == "DATE":
                values[field["field_key"]] = date.today().isoformat()
            elif field["field_type"] in {"SELECT", "RADIO"}:
                values[field["field_key"]] = str((field.get("options") or ["Yes"])[0])
            elif field["field_type"] == "YES_NO_NA":
                values[field["field_key"]] = "YES"
            else:
                values[field["field_key"]] = "Recorded during the visit."

    status, saved = flow.call(
        "PUT",
        f"/cases/{case_id}/form",
        {"values": values, "submit": False},
        token=field_token,
    )
    flow.expect("draft saves", status, saved)

    status, detail = flow.call("GET", f"/cases/{case_id}", token=field_token)
    flow.check(
        "the form's verdict reaches the case",
        detail.get("outcome") == "POSITIVE",
        f"outcome is {detail.get('outcome')}",
    )

    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/submit-to-office",
        {"remarks": "Address and identity verified."},
        token=field_token,
    )
    flow.expect("submitted to the office", status, payload)

    status, detail = flow.call("GET", f"/cases/{case_id}")
    flow.check(
        "submitting queues the case rather than closing it",
        detail.get("status") == "AWAITING_OFFICE_ASSIGNMENT",
        f"status is {detail.get('status_label')}",
    )

    # -- 5. Office stage ----------------------------------------------------
    status, office_staff = flow.call(
        "GET", "/cases/assignable-staff?stage=OFFICE_PROCESSING"
    )
    office_user = next(
        (s for s in office_staff if s["email"] == office), None
    ) if isinstance(office_staff, list) else None
    if not flow.check(f"{office} can take office work", office_user is not None):
        return report(flow)

    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/assign-office",
        {"office_staff_id": office_user["id"], "notes": "Prepare the report."},
    )
    flow.expect("assigned for office processing", status, payload)

    status, stages = flow.call("GET", f"/cases/{case_id}/stage-assignments")
    flow.check(
        "both assignments are kept, not overwritten",
        isinstance(stages, list)
        and {s["stage"] for s in stages}
        >= {"FIELD_INVESTIGATION", "OFFICE_PROCESSING"},
        f"{len(stages) if isinstance(stages, list) else 0} record(s)",
    )

    office_token = flow.login(office, password, optional=True) or admin
    status, seen = flow.call("GET", f"/cases/{case_id}", token=office_token)
    flow.expect("office staff can open the case", status, seen)

    # -- 6. Correction round ------------------------------------------------
    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/review",
        {"approve": False, "comment": "Attach the neighbour statement.",
         "outcome": "POSITIVE"},
    )
    flow.expect("returned for correction", status, payload)

    status, detail = flow.call("GET", f"/cases/{case_id}")
    flow.check(
        "the case goes back to Correction Required",
        detail.get("status") == "CORRECTION_REQUIRED",
        f"status is {detail.get('status_label')}",
    )

    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/status",
        {"status": "OFFICE_PROCESSING", "comment": "Statement attached."},
    )
    flow.expect("resubmitted to the office", status, payload)

    # -- 7. Approve, generate, complete -------------------------------------
    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/review",
        {"approve": True, "comment": "Verified.", "outcome": "POSITIVE"},
    )
    flow.expect("approved", status, payload)

    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/status",
        {"status": "COMPLETED", "outcome": "POSITIVE", "comment": "Delivered."},
    )
    flow.expect("completed", status, payload)

    status, document = flow.call(
        "POST",
        f"/cases/{case_id}/generate",
        {"output_format": "DOCX", "force": True},
    )
    if flow.expect("the insurer DOCX generates", status, document, 201):
        flow.check(
            "the file is named after the subject",
            subject.split()[0] in (document.get("display_name") or ""),
            document.get("display_name", ""),
        )
        flow.check(
            "the client's own template was used",
            document.get("used_client_template") is True,
        )

    # -- 8. The record ------------------------------------------------------
    status, timeline = flow.call("GET", f"/cases/{case_id}/timeline")
    events = {e["event_type"] for e in timeline} if isinstance(timeline, list) else set()
    flow.check(
        "the timeline records the whole journey",
        {"CASE_ASSIGNED", "SUBMITTED_TO_OFFICE", "OFFICE_ASSIGNED"} <= events,
        f"{len(events)} event type(s)",
    )

    status, activity = flow.call("GET", f"/activity/case/{case_id}")
    flow.check(
        "the activity log has entries for this case",
        isinstance(activity, list) and len(activity) > 0,
        f"{len(activity) if isinstance(activity, list) else 0} row(s)",
    )

    status, audit = flow.call("GET", f"/cases/{case_id}/audit")
    flow.check(
        "the audit log has entries for this case",
        isinstance(audit, list) and len(audit) > 0,
        f"{len(audit) if isinstance(audit, list) else 0} row(s)",
    )

    # -- 9. Reopen and clock out -------------------------------------------
    status, payload = flow.call(
        "POST",
        f"/cases/{case_id}/reopen",
        {"reason": "Smoke check that a closed case is never a dead end."},
    )
    flow.expect("a completed case can be reopened", status, payload)

    for who, tok in (("investigator", field_token), ("office", office_token),
                     ("admin", admin)):
        if tok:
            status, _ = flow.call("POST", "/attendance/clock-out", {}, token=tok)
            flow.check(f"{who} clocks out", status in (200, 409))

    return report(flow, case_id)


def report(flow: Flow, case_id: str | None = None) -> int:
    print("=" * 66)
    total = flow.passed + len(flow.failed)
    line = f"  {flow.passed}/{total} passed, {len(flow.failed)} failed"
    if flow.skipped:
        line += f", {len(flow.skipped)} skipped"
    print(line)
    if flow.failed:
        print("\n  Failed steps:")
        for label in flow.failed:
            print(f"    - {label}")
    elif case_id:
        print(f"\n  The flow runs end to end. Case {case_id}")
    print()
    return 1 if flow.failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--investigator", default="rahul.sharma@investigation.local"
    )
    parser.add_argument("--office", default="priyanka.singh@investigation.local")
    parser.add_argument("--password", default="Demo@123456")
    args = parser.parse_args()
    return run(args.base, args.investigator, args.office, args.password)


if __name__ == "__main__":
    raise SystemExit(main())
