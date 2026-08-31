# How a case moves through VIPL

One case, from the client's spreadsheet to a signed-off report. Every step
below is enforced by the server: a person who is not entitled to a step cannot
reach it by guessing a URL, and a status cannot be skipped.

---

## The chain

```
        Import                    Admin assigns
  client sheet ──────► Imported ─────────────────► Work in Progress
                                                          │
                                          investigator fills the form
                                                          │
                                                          ▼
                                             Submitted by Investigator
                                                          │
                                            Admin assigns office staff
                                                          │
                                                          ▼
                                              Report in Progress (RIP)
                                                          │
                                              office staff finish
                                                          │
                                                          ▼
                                                   Under Review
                                                     │        │
                                    Admin sends to   │        │  Admin approves
                                    quality check    │        │
                                                     ▼        ▼
                                             Quality Check   Verified
                                                     │        │
                                     back to review  │        ▼
                                                     └──► Completed
```

Quality check is a **detour the admin chooses**, not a compulsory stop. A case
may go from Under Review straight to Verified and then Completed.

---

## Who may do what

Permission is checked on the status itself, not on the screen. The rules live
in `STATUS_PERMISSIONS` in `backend/app/services/case_workflow.py`.

| Step | Who | Needs |
|---|---|---|
| Assign to an investigator | Admin, Manager | `case.assign` |
| Work and submit the case | The assigned investigator | assignee, or `case.edit` |
| Assign office staff | Admin, Manager | `case.assign_office` |
| Prepare the report | The office staff on the case | `case.process_office` |
| Hand back for review | That office staff | `case.process_office` |
| Send to quality check | Admin, Reviewer | `case.review` |
| Approve (Verified) | Admin, Reviewer | `case.review` |
| Complete | Admin, Reviewer | `case.complete` |
| Cancel | Admin | `case.delete` |

Two consequences worth stating plainly:

- **An investigator cannot complete their own case.** They can work it and
  submit it; everything past submission belongs to somebody else. This was
  previously possible and is now refused by the server.
- **Bulk status changes respect the same rules**, and only touch cases the
  person is allowed to see.

---

## Notifications

Each hand-off notifies the people who now have to act, and the bell plays a
short chime when the unread count rises. The sound can be turned off from the
bell panel; the choice is remembered on that device.

| When | Who is told |
|---|---|
| A case is assigned to you | The investigator |
| An investigator submits | Everyone with `case.assign_office` |
| Office staff are assigned | That office staff member |
| The report comes back for review | Everyone with `case.review` |
| A case is sent to quality check | Everyone with `case.review` |
| A case is returned for correction | The investigator |
| Verified or completed | The investigator |

The chime never fires on the first reading after sign-in, so a backlog of
unread items does not announce itself when the app opens.

---

## Importing

Death claim and investigation sheets arrive from different desks in different
layouts, so each has its own screen, reached from its own section of the
sidebar:

- **Investigation ▸ Import investigation cases**
- **Death Claim ▸ Import death claim cases**

A row belonging to the other queue is reported as an error naming the screen
it should have gone to, rather than being filed in the wrong place. The
combined `/imports` screen still accepts either kind.

### Dates

Client sheets disagree about date order. Most write `24-08-2026`; at least one
writes `8/24/2026`. The importer decides the order **once per file** by looking
for a component above twelve, which can only be a day. Per-cell guessing would
read `8/6/2026` as 8 June in an American sheet and silently move the case two
months. If a file gives no evidence either way, day-first is assumed.

### Case types

An insurer's own wording is matched through aliases, so Aditya Birla's
"Project Verification", "Physical Verification" and "Post Verification" all
route to their one Pre-Issuance form. The sheet's original wording stays
visible on the case's **Imported data** tab.

---

## Evidence

Photographs can be added two ways:

- **Overview ▸ Photographs** — several at once, each stamped with the location
  read when the panel opened. Uploads run one after another, and one rejected
  file does not discard the rest.
- **Documents ▸ Upload evidence** — the camera dialog, for taking a picture on
  the spot with a live viewfinder.

The camera needs HTTPS. Without a certificate the browser refuses to open it.

---

## Documents

A generated DOCX contains **only what was actually filled in**. Fields left
empty come out empty; the insurer's specimen values never appear. This is
checked by `backend/tests/test_document_output.py`.

Generation needs the template's *tagged copy*, produced by
`scripts.tag_templates`. If it is missing the DOCX button reports it; run
`python -m scripts.doctor` to see the state of every template at once.

---

## Retention

Cases older than `DATA_RETENTION_DAYS` (90 by default) disappear from the
normal lists but stay in the database. Tick **Include archived** on the case
list to see them.
