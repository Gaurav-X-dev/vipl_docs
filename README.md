# Investigation & Death Claim Case Management System

A case management system for a bank/insurance investigation agency. The daily
Excel from the client becomes cases automatically, bank-supplied fields are
pre-filled into the right insurer's form, an investigator completes the rest,
a reviewer approves it, and the completed case is rendered back into the
client's own Word document.

Built from the client's supplied material — 20 insurer forms, two handwritten
dashboard specifications and one raw Excel header sample. Every field, status
and column name traces back to one of them; see
[`docs/ATTACHMENT_ANALYSIS.md`](docs/ATTACHMENT_ANALYSIS.md).

---

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Setup](#setup)
- [Running it](#running-it)
- [Development login](#development-login)
- [The two-stage workflow](#the-two-stage-workflow)
- [Company-wise navigation](#company-wise-navigation)
- [Client-supplied data and retention](#client-supplied-data-and-retention)
- [Attendance and activity](#attendance-and-activity)
- [Daily Excel import](#daily-excel-import)
- [Document templates](#document-templates)
- [Tests and checks](#tests-and-checks)
- [Production considerations](#production-considerations)
- [Project layout](#project-layout)

---

## What it does

```
Bank / insurance company
        │  daily Excel or CSV
        ▼
   Import  ──► validate every row ──► preview ──► confirm
        │
        ▼
   Cases created automatically and routed to
   Investigation ▸ <Company>  or  Death Claim ▸ <Company>
        │            (the sidebar builds itself from the data)
        ▼
   Bank-supplied fields are pre-filled and LOCKED 🔒
        │
        ▼
   STAGE 1 — assign a Field Investigator
        │      visit ▸ fill the insurer's own form ▸ upload evidence
        ▼
   Submit to office  ──►  Awaiting Office Assignment
        │                 (submitting never completes a case)
        ▼
   STAGE 2 — assign Office Staff
        │      verify ▸ complete office sections ▸ request correction ↺
        ▼
   Review ──► Approve ──► generate the insurer's own DOCX / PDF
        │
        ▼
   Completed ──► export to Excel
```

Alongside every case, the system tracks the people doing the work: **Clock In /
Clock Out** attendance (kept separate from online/offline presence) and a full
**user activity log** the Super Admin can filter by person, module, case or date.

Everything above is audited, and every case carries a plain-language timeline.

**Modules**: Dashboard · My Cases · Case management (Investigation + Death
Claims, navigated company-by-company) · Excel/CSV import · Staff · Attendance ·
Activity log · HR · Companies & case types · Form and document templates ·
Reports · Audit log · Administration.

---

## Architecture

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 |
| Database | PostgreSQL 16+ (`asyncpg`) |
| Frontend | React 19, TypeScript, Vite, TanStack Query, React Router |
| Auth | JWT access + refresh tokens, Argon2 password hashing, DB-backed sessions |
| Documents | `docxtpl` for the client's Word forms, ReportLab for PDF |
| Spreadsheets | `openpyxl` |

The backend is layered: `api → services → models`. Business rules live in
services so they are enforced identically however they are reached, and the
case status machine is a pure, unit-tested module.

More detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Requirements

- **Python 3.12 or newer** (verified on 3.14)
- **Node.js 20 or newer** (verified on 24)
- **PostgreSQL 16 or newer**

---

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements-dev.txt

copy .env.example .env            # Windows
# cp .env.example .env            # macOS / Linux
```

Edit `backend/.env` and set at least:

```ini
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/investigation_db
SECRET_KEY=<a long random string>
SUPER_ADMIN_EMAIL=admin@investigation.local
SUPER_ADMIN_PASSWORD=Admin@123456
```

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. Database

Create the database, then run the migrations:

```bash
createdb -U postgres investigation_db
# or:  psql -U postgres -c "CREATE DATABASE investigation_db;"

cd backend
alembic upgrade head
```

If no migration file exists yet (first run on a fresh clone), generate it once:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 3. Seed

```bash
python -m scripts.seed          # roles, permissions, companies, case types,
                                # form templates, document templates, Super Admin
python -m scripts.seed --demo   # the above plus demo staff and sample cases
```

Seeding is idempotent — running it again updates masters and never duplicates
them. An existing Super Admin password is never reset.

### 4. Frontend

```bash
cd frontend
npm install
copy .env.example .env          # optional; the dev proxy works without it
```

---

## Running it

Two terminals:

```bash
# terminal 1 — API on http://127.0.0.1:8000
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload

# terminal 2 — web app on http://localhost:5173
cd frontend
npm run dev
```

Open **http://localhost:5173**.

- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

The Vite dev server proxies `/api` and `/health` to the backend, so no CORS
configuration is needed while developing.

### Running without PostgreSQL

For a quick look with no database server, point `DATABASE_URL` at SQLite and
create the schema directly:

```ini
DATABASE_URL=sqlite+aiosqlite:///./vipl_dev.db
```

```bash
pip install aiosqlite
python -m scripts.init_db
python -m scripts.seed --demo
```

This is a convenience for local exploration only. PostgreSQL is the supported
database: JSONB, concurrent-safe case numbering and the migration history all
assume it.

---

## Development login

```
Email:    admin@investigation.local
Password: Admin@123456
```

Both come from `SUPER_ADMIN_EMAIL` / `SUPER_ADMIN_PASSWORD` in `backend/.env`.
**Change them before any production deployment.** They are never written to
source, and the password is stored only as an Argon2 hash.

With `--demo` seeding you also get staff logins, all with password
`Demo@123456`:

| Email | Role |
|-------|------|
| `rahul.sharma@investigation.local` | Investigator |
| `anita.verma@investigation.local` | Investigator |
| `imran.qureshi@investigation.local` | Investigator |
| `vikas.mehta@investigation.local` | Reviewer |
| `priya.deshmukh@investigation.local` | Manager |
| `sneha.nair@investigation.local` | Data Entry Operator |
| `farhan.ali@investigation.local` | HR |
| `priyanka.singh@investigation.local` | Office Staff |
| `arjun.rao@investigation.local` | Office Staff |

Sign in as an investigator to see role scoping in action: their sidebar, case
list, dashboard counts and activity log are all limited to their own desk. Sign
in as Office Staff to see the same case from the other side of the hand-off.

---

## The two-stage workflow

A case is worked twice, by two different people, and the first assignment is
never replaced by the second.

```
Imported ▸ Unassigned
      ↓  assign investigator
Assigned ▸ Accepted ▸ WIP ▸ Field Investigation ▸ Documents Pending ▸ RIP
      ↓  Submit to office   (requires an outcome; does NOT complete the case)
Awaiting Office Assignment
      ↓  assign office staff
Office Processing
      ↓
Under Review ⇄ Correction Required
      ↓  approve
Verified ▸ Document Generated ▸ Completed
```

Both assignments live in `case_assignments` with a `stage`
(`FIELD_INVESTIGATION` / `OFFICE_PROCESSING` / `REVIEW`) and a `state`. Reassigning
marks the outgoing row `RELEASED` and appends a new one, so "who held this case
in March" always has an answer. The **Workflow** tab on any case shows the track
and the full custody chain.

Visit progress (`Not Started → Visit Scheduled → … → Submitted to Office`) is
tracked separately from the case status, because a case can be in WIP while the
visit itself has not started.

---

## Company-wise navigation

The sidebar is generated, not hand-written. `GET /api/v1/navigation/sidebar`
returns one branch per category and, inside it, **every company configured with
an active form template** — with a live count beside those that have work:

```
Investigation (4)
   All investigation cases
   ├── Aditya Birla Life
   ├── Bajaj Allianz Life
   ├── Canara HSBC Life      1
   ├── HDFC Life             1
   └── ICICI Prudential      1

Death Claim (1)
   └── … the same structure
```

Two deliberate choices:

* **Names only.** No status rows under each company. The people using this all
  day navigate by client first, and the status filters already live on the case
  list where they can be combined with everything else.
* **The list is fixed by configuration, not by today's data.** A company with
  no open work still stands in the menu, so tomorrow's file lands somewhere the
  operator already knows to look, and the menu does not reshuffle as cases
  complete.

Adding a company plus a form template puts it in the sidebar. No code change.

Counts come from one grouped aggregate per category, are scoped to what the
signed-in user may see, and honour the retention window — case rows are never
loaded into the browser to compute a menu number.

---

## Client-supplied data and retention

Values that arrive in the daily file are **marked, not locked**. The Imported
data tab shows where each one came from — which spreadsheet column, and when —
and the original is kept beside the current value. Staff correct a wrong policy
number on the spot; the change lands in the field history, the audit log and
the case timeline, so nothing moves invisibly.

There is deliberately no unlock step: making someone chase a Super Admin to fix
a typo cost more than it protected.

### The 90-day window

Cases that have been closed for longer than `data_retention_days` (90 by
default, editable under Administration → Settings) drop out of the working
views: the case list, the sidebar counts and the dashboards.

They are **not deleted**. The case, its form, its evidence, its generated
documents and its whole audit trail stay in the database. Tick **Include
archived** on the case list to bring them back into view, or query them
directly. The cut-off is computed on every request, so a case ages out exactly
on its ninetieth day with no job to schedule and nothing to go stale.

`scripts/purge_old_data.py` still exists for the separate case of genuinely
deleting old records, and it is opt-in.

---

## Attendance and activity

Two things the client asked to keep strictly apart:

| | Meaning | Source |
|---|---|---|
| **Online / Offline** | The browser is active | `users.last_activity_at` heartbeat |
| **Clocked In / Clocked Out** | The person is on shift | `attendance_sessions` |

Someone can be Online and Clocked Out (checking email from home) or Offline and
Clocked In (out on a visit). Both are displayed; neither is inferred from the
other, and **signing in never starts the clock**.

The clock lives in the header on every screen. It refuses a second clock-in while
a shift is open, refuses a clock-out with no shift, and closes a shift left open
overnight at the end of its own working day, flagged `auto_closed` so the
correction is visible rather than silently inflating hours.

The **Activity log** records what people did — opened a case, saved a draft,
generated a report — as distinct from the **Audit log**, which records what data
changed. The Super Admin can filter activity by user, module, action, case or
date; everyone else sees only their own.

---

## Daily Excel import

**Case Management → Import Cases**, or `/imports`.

1. Upload the client's `.xlsx`, `.xlsm` or `.csv`.
2. Every row is parsed and validated on the server. You get a preview split
   into Valid / Warnings / Errors / Duplicates, plus the column mapping that
   was applied.
3. Download the rejected rows as a workbook if anything failed — it contains
   the row number, the original data and the error message.
4. Confirm. Cases are created in a single transaction: either all accepted
   rows become cases, or none do.
5. A completed batch can be rolled back while no work has started on its cases.

The expected columns are in [`samples/case_import_template.xlsx`](samples/) and
documented in [`samples/import_mapping_notes.md`](samples/import_mapping_notes.md).
Header matching ignores case, spacing and punctuation, and accepts the aliases
configured per column — so `Life_Assured_Name`, `Life Assured Name` and
`LA Name` all resolve to the same field.

Re-uploading a file that has already been committed is refused by checksum.

### The client's Status column

The daily file usually carries a `Status` column. That is the *client's* record
of where they think the case is — it is not our workflow position, and a file
saying `Completed` must not create a case nobody can work on.

So by default the value is **kept as a note on the case** (`import_remark`) and
every new case starts at `Imported`, ready to be assigned. The preview says so
per row before you commit.

Loading genuinely historic, already-closed records is a different job, and the
confirm screen has a checkbox for it: **Use the Status column from the file**.
Leave it off for the daily import.

A case closed by mistake is not a dead end — anyone with `case.edit` can
**Reopen case** from the case header. Reopening asks for a reason, clears the
completion dates, and returns the case to whoever last held it: office staff if
it had reached the office, otherwise the investigator. The reason lands in the
timeline and the audit log.

---

## Document templates

The 20 insurer forms supplied with the project are registered automatically by
the seed script and stored under `storage/document_templates/original/`. They
are never modified.

Those files are *completed specimen reports*, not blank templates. To make one
fillable:

```bash
cd backend
python -m scripts.tag_templates --dry-run   # show what would be replaced
python -m scripts.tag_templates             # write the tagged copies
```

This writes a tagged copy to `storage/document_templates/tagged/` where the
specimen values have become `{{ placeholders }}`, and prints every substitution
so the mapping is auditable. Long narrative paragraphs are deliberately left
alone: open the tagged file in Word once, replace the remark blocks with
`{{ vicinity_remarks }}`, `{{ overall_remarks }}` and `{{ conclusion }}`, and
upload it as a new version from **Templates → Document templates**.

Generation is version-pinned: a case completed against version 1 keeps
rendering version 1 even after version 2 is uploaded.

`investigation_docs/HDFC Pre claim.doc` is a legacy Word 97-2003 binary file
that cannot be filled programmatically. It is registered with status
`NEEDS_CONVERSION` and flagged in the UI; PDF generation still works for it.

Full detail: [`docs/DOCUMENT_GENERATION.md`](docs/DOCUMENT_GENERATION.md).

---

## Tests and checks

```bash
# backend
cd backend
pytest                       # unit + full acceptance-scenario integration tests
ruff check app scripts tests # lint

# frontend
cd frontend
npm run lint
npm run build                # type-checks and produces a production build
```

The backend suite runs against in-memory SQLite, so it needs no database
server. It covers the whole acceptance scenario end to end: login → import →
validation → assignment → form fill → evidence upload → submit → review →
complete → document generation → audit → export, plus the workflow, permission
and duplicate-protection rules.

### The live flow check

Unit tests pass in isolation; the flow can still be broken for a real user.
`scripts/smoke_flow.py` drives one case through the entire day against a
**running server**, over HTTP, exactly as the browser does:

```bash
cd backend
python -m scripts.smoke_flow
python -m scripts.smoke_flow --password 'YourStaffPassword'
```

It signs in, clocks in, imports a file, assigns a field investigator, records a
visit, fills and submits the form, hands the case to the office, returns it for
correction, approves it, generates the insurer document and clocks everyone out
— printing PASS or FAIL for each of about forty steps. Anything other than
`0 failed` means the flow is broken for a real user whatever `pytest` says.

It found the bug where a *second* clock-in on the same day answered HTTP 500,
which no unit test had reached.

Staff passwords can be changed outside the script; when a staff sign-in fails
the run reports SKIP and continues as the admin rather than stopping, so one
changed password never hides a real fault.

---

## Production considerations

Before going live:

1. **Credentials** — change `SUPER_ADMIN_PASSWORD`, set a strong `SECRET_KEY`,
   use a dedicated database role rather than `postgres`.
2. **`APP_ENV=production`, `DEBUG=false`** — this also hides `/docs` and
   `/openapi.json`, and stops error responses from including exception detail.
3. **TLS** — terminate HTTPS at a reverse proxy and set `FRONTEND_URL` /
   `CORS_ORIGINS` to the real origins.
4. **Storage** — `storage/` holds evidence, generated documents and template
   originals. Put it on durable, backed-up storage.
5. **Backups** — PostgreSQL plus the `storage/` tree.
6. **Retention** — Image 2 asks for "90 days data remove". Schedule
   `python -m scripts.purge_old_data --confirm` and confirm the window under
   **Administration → Settings → Data retention**. Always run `--dry-run` first.
7. **Workers** — run uvicorn behind a process manager, or `gunicorn -k
   uvicorn.workers.UvicornWorker`.
8. **PDF fidelity** — installing LibreOffice on the server makes PDF exports
   render from the insurer's own Word layout. Without it, PDFs use the built-in
   report layout instead.

Security detail: [`docs/SECURITY.md`](docs/SECURITY.md).

---

## Project layout

```
vipl/
├── backend/
│   ├── alembic/                 database migrations
│   ├── app/
│   │   ├── api/v1/              route handlers, one module per area
│   │   ├── core/                config, security, permissions, errors
│   │   ├── db/                  engine, session, declarative base
│   │   ├── documents/           DOCX rendering, PDF, template tagging
│   │   ├── imports/             spreadsheet parsing and column mapping
│   │   ├── models/              SQLAlchemy models (40 tables)
│   │   ├── schemas/             Pydantic request/response models
│   │   ├── seeds/               companies, case types, form definitions
│   │   ├── services/            business logic
│   │   └── utils/               dates, text, safe file handling
│   ├── scripts/                 seed, tag_templates, smoke_flow,
│   │                            reset_cases, fix_duplicate_fields, purge
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/               one screen per module
│       ├── components.tsx       shared presentational pieces
│       ├── ui.tsx               modal, form, tabs, toast primitives
│       ├── layout.tsx           dynamic sidebar, header, clock, notifications
│       ├── office.tsx           two-stage assignment dialogs and staff picker
│       ├── casestage.tsx        workflow tab, visit, submit, locked data panel
│       └── types.ts             API contract types
├── docs/                        analysis and design documentation
├── samples/                     import template and mapping notes
├── investigation_docs/          the client's 14 investigation forms
├── death_claim_docs/            the client's 6 death claim forms
└── storage/                     uploads, generated documents, templates
```
