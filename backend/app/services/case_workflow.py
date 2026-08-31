"""Case status machine, display labels and TAT computation.

Pure functions — no database access — so the rules are unit-testable and are
enforced identically wherever a status changes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.errors import WorkflowError
from app.models.enums import (
    CLOSED_STATUSES,
    AssignmentStage,
    CaseOutcome,
    CaseStatus,
    TatState,
    VisitStatus,
)
from app.utils.dates import ensure_utc, utcnow

#: Human labels — the client's own wording, expanded for readability.
STATUS_LABELS: dict[CaseStatus, str] = {
    CaseStatus.IMPORTED: "Imported",
    CaseStatus.UNASSIGNED: "Unassigned",
    CaseStatus.ASSIGNED: "Assigned",
    CaseStatus.ACCEPTED: "Accepted",
    CaseStatus.WIP: "Work in Progress (WIP)",
    CaseStatus.FIELD_INVESTIGATION: "Field Investigation",
    CaseStatus.DOCUMENTS_PENDING: "Documents Pending",
    CaseStatus.RIP: "Field Report Drafting",
    CaseStatus.REPORT_SUBMITTED: "Submitted by Investigator",
    CaseStatus.AWAITING_OFFICE_ASSIGNMENT: "Awaiting Office Assignment",
    CaseStatus.OFFICE_PROCESSING: "Report in Progress (RIP)",
    CaseStatus.UNDER_REVIEW: "Under Review",
    CaseStatus.QUALITY_CHECK: "Quality Check",
    CaseStatus.CORRECTION_REQUIRED: "Correction Required",
    CaseStatus.VERIFIED: "Verified",
    CaseStatus.COMPLETED: "Completed",
    CaseStatus.REJECTED: "Rejected",
    CaseStatus.CANCELLED: "Cancelled",
}

#: Colour token consumed by the frontend badge component.
STATUS_TONE: dict[CaseStatus, str] = {
    CaseStatus.IMPORTED: "neutral",
    CaseStatus.UNASSIGNED: "warning",
    CaseStatus.ASSIGNED: "info",
    CaseStatus.ACCEPTED: "info",
    CaseStatus.WIP: "info",
    CaseStatus.FIELD_INVESTIGATION: "info",
    CaseStatus.DOCUMENTS_PENDING: "warning",
    CaseStatus.RIP: "info",
    CaseStatus.REPORT_SUBMITTED: "info",
    CaseStatus.AWAITING_OFFICE_ASSIGNMENT: "warning",
    CaseStatus.OFFICE_PROCESSING: "info",
    CaseStatus.UNDER_REVIEW: "info",
    CaseStatus.QUALITY_CHECK: "warning",
    CaseStatus.CORRECTION_REQUIRED: "warning",
    CaseStatus.VERIFIED: "success",
    CaseStatus.COMPLETED: "success",
    CaseStatus.REJECTED: "danger",
    CaseStatus.CANCELLED: "neutral",
}

#: Allowed transitions. Anything not listed here is refused server-side.
TRANSITIONS: dict[CaseStatus, tuple[CaseStatus, ...]] = {
    CaseStatus.IMPORTED: (
        CaseStatus.UNASSIGNED,
        CaseStatus.ASSIGNED,
        CaseStatus.WIP,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.UNASSIGNED: (
        CaseStatus.ASSIGNED,
        CaseStatus.WIP,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.ASSIGNED: (
        CaseStatus.ACCEPTED,
        CaseStatus.WIP,
        CaseStatus.UNASSIGNED,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.ACCEPTED: (
        CaseStatus.WIP,
        CaseStatus.FIELD_INVESTIGATION,
        CaseStatus.UNASSIGNED,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.WIP: (
        CaseStatus.FIELD_INVESTIGATION,
        CaseStatus.DOCUMENTS_PENDING,
        CaseStatus.RIP,
        CaseStatus.UNASSIGNED,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.FIELD_INVESTIGATION: (
        CaseStatus.DOCUMENTS_PENDING,
        CaseStatus.RIP,
        CaseStatus.WIP,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.DOCUMENTS_PENDING: (
        CaseStatus.RIP,
        CaseStatus.FIELD_INVESTIGATION,
        CaseStatus.WIP,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.RIP: (
        CaseStatus.REPORT_SUBMITTED,
        CaseStatus.WIP,
        CaseStatus.DOCUMENTS_PENDING,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.REPORT_SUBMITTED: (
        CaseStatus.AWAITING_OFFICE_ASSIGNMENT,
        CaseStatus.OFFICE_PROCESSING,
        CaseStatus.UNDER_REVIEW,
        CaseStatus.CORRECTION_REQUIRED,
        CaseStatus.VERIFIED,
        CaseStatus.REJECTED,
    ),
    CaseStatus.AWAITING_OFFICE_ASSIGNMENT: (
        CaseStatus.OFFICE_PROCESSING,
        CaseStatus.CORRECTION_REQUIRED,
        CaseStatus.UNDER_REVIEW,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.OFFICE_PROCESSING: (
        CaseStatus.UNDER_REVIEW,
        CaseStatus.QUALITY_CHECK,
        CaseStatus.CORRECTION_REQUIRED,
        CaseStatus.VERIFIED,
        CaseStatus.AWAITING_OFFICE_ASSIGNMENT,
        CaseStatus.REJECTED,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.UNDER_REVIEW: (
        CaseStatus.QUALITY_CHECK,
        CaseStatus.VERIFIED,
        CaseStatus.CORRECTION_REQUIRED,
        CaseStatus.OFFICE_PROCESSING,
        CaseStatus.REJECTED,
    ),
    # Quality check is the optional detour the admin chooses instead of
    # completing straight away; it always hands the case back to them.
    CaseStatus.QUALITY_CHECK: (
        CaseStatus.UNDER_REVIEW,
        CaseStatus.VERIFIED,
        CaseStatus.CORRECTION_REQUIRED,
        CaseStatus.OFFICE_PROCESSING,
        CaseStatus.REJECTED,
    ),
    CaseStatus.CORRECTION_REQUIRED: (
        CaseStatus.QUALITY_CHECK,
        CaseStatus.RIP,
        CaseStatus.WIP,
        CaseStatus.FIELD_INVESTIGATION,
        CaseStatus.REPORT_SUBMITTED,
        CaseStatus.OFFICE_PROCESSING,
        CaseStatus.CANCELLED,
    ),
    CaseStatus.VERIFIED: (CaseStatus.COMPLETED, CaseStatus.CORRECTION_REQUIRED),
    CaseStatus.COMPLETED: (),
    CaseStatus.REJECTED: (),
    CaseStatus.CANCELLED: (),
}

#: Which permission lets somebody move a case *into* each status.
#:
#: Without this the status endpoint asked only for ``case.view``, so anyone who
#: could open a case could also drive it to Completed — past the office stage,
#: past review and past quality check. Holding any one of the listed codes is
#: enough; Super Admins bypass the check, and the investigator the case is
#: assigned to may move it through their own field stage (see
#: ``ASSIGNEE_MAY_SET``).
STATUS_PERMISSIONS: dict[CaseStatus, frozenset[str]] = {
    CaseStatus.IMPORTED: frozenset({"case.edit"}),
    CaseStatus.UNASSIGNED: frozenset({"case.assign", "case.reassign"}),
    CaseStatus.ASSIGNED: frozenset({"case.assign", "case.reassign"}),
    CaseStatus.ACCEPTED: frozenset({"case.edit"}),
    CaseStatus.WIP: frozenset({"case.edit"}),
    CaseStatus.FIELD_INVESTIGATION: frozenset({"case.edit"}),
    CaseStatus.DOCUMENTS_PENDING: frozenset({"case.edit"}),
    CaseStatus.RIP: frozenset({"case.edit"}),
    CaseStatus.REPORT_SUBMITTED: frozenset({"case.edit"}),
    CaseStatus.AWAITING_OFFICE_ASSIGNMENT: frozenset(
        {"case.assign_office", "case.process_office", "case.edit"}
    ),
    CaseStatus.OFFICE_PROCESSING: frozenset({"case.assign_office", "case.process_office"}),
    # Office staff hand the finished report back to the admin themselves.
    CaseStatus.UNDER_REVIEW: frozenset({"case.process_office", "case.review"}),
    CaseStatus.QUALITY_CHECK: frozenset({"case.review"}),
    CaseStatus.CORRECTION_REQUIRED: frozenset({"case.review"}),
    CaseStatus.VERIFIED: frozenset({"case.review"}),
    CaseStatus.REJECTED: frozenset({"case.review"}),
    CaseStatus.COMPLETED: frozenset({"case.complete"}),
    CaseStatus.CANCELLED: frozenset({"case.delete"}),
}

#: Statuses the assigned investigator may set on their own case without
#: holding a wider editing permission. Their whole job is to move a case
#: through these.
#: Spelled out rather than derived from FIELD_STAGE_STATUSES, which is
#: defined further down this module. It is that set minus ASSIGNED, plus
#: REPORT_SUBMITTED: an investigator works and submits their own case, but
#: assigning it is somebody else's decision.
ASSIGNEE_MAY_SET: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.ACCEPTED,
        CaseStatus.WIP,
        CaseStatus.FIELD_INVESTIGATION,
        CaseStatus.DOCUMENTS_PENDING,
        CaseStatus.RIP,
        CaseStatus.REPORT_SUBMITTED,
    }
)


def may_set_status(
    target: CaseStatus,
    *,
    permission_codes: set[str] | frozenset[str],
    is_super_admin: bool = False,
    is_assignee: bool = False,
    is_office_staff: bool = False,
) -> bool:
    """Whether this person is allowed to move a case into ``target``."""
    if is_super_admin:
        return True
    if is_assignee and target in ASSIGNEE_MAY_SET:
        return True
    # The office staff member the case sits with may return it for review.
    if is_office_staff and target in {
        CaseStatus.UNDER_REVIEW,
        CaseStatus.OFFICE_PROCESSING,
    }:
        return True
    return bool(STATUS_PERMISSIONS.get(target, frozenset()) & set(permission_codes))


#: Image 2: "report in progress -> if done -> negative / positive / suspicious".
#: A report cannot leave the investigator's hands without an outcome.
STATUSES_REQUIRING_OUTCOME: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.REPORT_SUBMITTED,
        CaseStatus.VERIFIED,
        CaseStatus.COMPLETED,
    }
)


def status_label(status: CaseStatus) -> str:
    return STATUS_LABELS.get(status, status.value.replace("_", " ").title())


def allowed_transitions(status: CaseStatus) -> tuple[CaseStatus, ...]:
    return TRANSITIONS.get(status, ())


def can_transition(current: CaseStatus, target: CaseStatus) -> bool:
    return target in allowed_transitions(current)


def assert_transition(
    current: CaseStatus, target: CaseStatus, outcome: CaseOutcome | None = None
) -> None:
    """Raise :class:`WorkflowError` unless the transition is legal."""
    if current == target:
        raise WorkflowError(f"The case is already {status_label(target)}.")
    if current in CLOSED_STATUSES:
        raise WorkflowError(f"{status_label(current)} is a final state and cannot be changed.")
    if not can_transition(current, target):
        allowed = ", ".join(status_label(s) for s in allowed_transitions(current))
        raise WorkflowError(
            f"Cannot move from {status_label(current)} to {status_label(target)}.",
            details={"allowed": allowed or "none"},
        )
    if target in STATUSES_REQUIRING_OUTCOME and outcome is None:
        raise WorkflowError(
            "An outcome of Positive, Negative or Suspicious is required before "
            f"moving the case to {status_label(target)}."
        )


def is_open(status: CaseStatus) -> bool:
    return status not in CLOSED_STATUSES


# --------------------------------------------------------------------------- #
# TAT
# --------------------------------------------------------------------------- #
def compute_due_at(
    received_at: datetime, tat_days: int, explicit_due: datetime | None = None
) -> datetime:
    if explicit_due is not None:
        return explicit_due
    base = ensure_utc(received_at) or utcnow()
    return base + timedelta(days=max(1, tat_days))


def tat_state(
    status: CaseStatus,
    due_at: datetime | None,
    completed_at: datetime | None,
    warning_hours: int,
    now: datetime | None = None,
) -> TatState:
    """Classify a case as In TAT / About to breach / Out of TAT (Image 1)."""
    if due_at is None:
        return TatState.NOT_APPLICABLE
    reference = ensure_utc(completed_at) or ensure_utc(now) or utcnow()
    due = ensure_utc(due_at)
    if due is None:
        return TatState.NOT_APPLICABLE

    if status in CLOSED_STATUSES:
        if status != CaseStatus.COMPLETED:
            return TatState.NOT_APPLICABLE
        return TatState.IN_TAT if reference <= due else TatState.OUT_OF_TAT

    if reference > due:
        return TatState.OUT_OF_TAT
    if due - reference <= timedelta(hours=max(0, warning_hours)):
        return TatState.ABOUT_TO_BREACH
    return TatState.IN_TAT


def tat_days_remaining(
    due_at: datetime | None, completed_at: datetime | None, now: datetime | None = None
) -> int | None:
    if due_at is None:
        return None
    reference = ensure_utc(completed_at) or ensure_utc(now) or utcnow()
    due = ensure_utc(due_at)
    if due is None:
        return None
    return (due - reference).days


def aging_days(
    received_at: datetime | None,
    completed_at: datetime | None = None,
    now: datetime | None = None,
) -> int | None:
    """Client's "Aging" column: days the case has been with the agency."""
    start = ensure_utc(received_at)
    if start is None:
        return None
    end = ensure_utc(completed_at) or ensure_utc(now) or utcnow()
    return max(0, (end - start).days)


def path_to(current: CaseStatus, target: CaseStatus) -> list[CaseStatus]:
    """The shortest legal run of statuses from ``current`` to ``target``.

    The machine only allows one step at a time, which is right — it is what
    stops a case skipping review. But a caller that wants to move a case two
    or three legal steps should not have to know the intermediate names, and
    an investigator pressing Submit on a freshly assigned case should not be
    told "Cannot move from Assigned to Submitted by Investigator".

    Returns the steps *after* ``current``, or an empty list when no legal run
    exists.
    """
    if current == target:
        return []
    seen = {current}
    queue: list[tuple[CaseStatus, list[CaseStatus]]] = [(current, [])]
    while queue:
        node, route = queue.pop(0)
        for nxt in allowed_transitions(node):
            if nxt in seen:
                continue
            step = [*route, nxt]
            if nxt == target:
                return step
            seen.add(nxt)
            queue.append((nxt, step))
    return []


def status_after_assignment(current: CaseStatus) -> CaseStatus:
    """Assignment puts the case straight into Work in Progress.

    The agency treats handing a case to an investigator as the work starting:
    there is no waiting room between the two, and a separate Assigned state
    only produced a column nobody acted on. Live work is left alone.
    """
    if current in {CaseStatus.IMPORTED, CaseStatus.UNASSIGNED, CaseStatus.ASSIGNED}:
        return CaseStatus.WIP
    return current


# --------------------------------------------------------------------------- #
# Two-stage workflow
# --------------------------------------------------------------------------- #
#: Statuses in which the field investigator owns the case.
FIELD_STAGE_STATUSES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.ASSIGNED,
        CaseStatus.ACCEPTED,
        CaseStatus.WIP,
        CaseStatus.FIELD_INVESTIGATION,
        CaseStatus.DOCUMENTS_PENDING,
        CaseStatus.RIP,
    }
)

#: Statuses in which the back office owns the case.
OFFICE_STAGE_STATUSES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.AWAITING_OFFICE_ASSIGNMENT,
        CaseStatus.OFFICE_PROCESSING,
    }
)

#: Statuses in which a reviewer owns the case.
REVIEW_STAGE_STATUSES: frozenset[CaseStatus] = frozenset(
    {CaseStatus.UNDER_REVIEW, CaseStatus.VERIFIED}
)

VISIT_STATUS_LABELS: dict[VisitStatus, str] = {
    VisitStatus.NOT_STARTED: "Not Started",
    VisitStatus.VISIT_SCHEDULED: "Visit Scheduled",
    VisitStatus.VISIT_IN_PROGRESS: "Visit In Progress",
    VisitStatus.VISITED: "Visited",
    VisitStatus.INFORMATION_COLLECTED: "Information Collected",
    VisitStatus.FORM_COMPLETED: "Form Completed",
    VisitStatus.SUBMITTED_TO_OFFICE: "Submitted to Office",
}

#: Forward-only visit progression; each step may skip ahead but never back.
VISIT_ORDER: tuple[VisitStatus, ...] = (
    VisitStatus.NOT_STARTED,
    VisitStatus.VISIT_SCHEDULED,
    VisitStatus.VISIT_IN_PROGRESS,
    VisitStatus.VISITED,
    VisitStatus.INFORMATION_COLLECTED,
    VisitStatus.FORM_COMPLETED,
    VisitStatus.SUBMITTED_TO_OFFICE,
)


def visit_label(status: VisitStatus) -> str:
    return VISIT_STATUS_LABELS.get(status, status.value.replace("_", " ").title())


def current_stage(status: CaseStatus) -> AssignmentStage | None:
    """Which desk the case is sitting on right now."""
    if status in FIELD_STAGE_STATUSES:
        return AssignmentStage.FIELD_INVESTIGATION
    if status in OFFICE_STAGE_STATUSES:
        return AssignmentStage.OFFICE_PROCESSING
    if status in REVIEW_STAGE_STATUSES:
        return AssignmentStage.REVIEW
    if status == CaseStatus.REPORT_SUBMITTED:
        return AssignmentStage.OFFICE_PROCESSING
    if status == CaseStatus.CORRECTION_REQUIRED:
        return AssignmentStage.FIELD_INVESTIGATION
    return None


def status_after_field_submission() -> CaseStatus:
    """Submitting from the field never completes a case — it queues it."""
    return CaseStatus.AWAITING_OFFICE_ASSIGNMENT


def status_after_office_assignment(current: CaseStatus) -> CaseStatus:
    if current in {
        CaseStatus.REPORT_SUBMITTED,
        CaseStatus.AWAITING_OFFICE_ASSIGNMENT,
    }:
        return CaseStatus.OFFICE_PROCESSING
    return current


def assert_office_assignable(status: CaseStatus) -> None:
    """Office staff take over only once the field work has been handed in."""
    if status in CLOSED_STATUSES:
        raise WorkflowError(f"{status_label(status)} is a final state and cannot be assigned.")
    if status not in {
        CaseStatus.REPORT_SUBMITTED,
        CaseStatus.AWAITING_OFFICE_ASSIGNMENT,
        CaseStatus.OFFICE_PROCESSING,
        CaseStatus.UNDER_REVIEW,
        CaseStatus.CORRECTION_REQUIRED,
    }:
        raise WorkflowError(
            "The investigator has not submitted this case to the office yet. "
            f"It is currently {status_label(status)}."
        )


def assert_field_submittable(status: CaseStatus) -> None:
    if status in CLOSED_STATUSES:
        raise WorkflowError(f"{status_label(status)} is a final state and cannot be submitted.")
    if status not in FIELD_STAGE_STATUSES | {CaseStatus.CORRECTION_REQUIRED}:
        raise WorkflowError(
            "Only a case that is with the field investigator can be submitted "
            f"to the office. This one is {status_label(status)}."
        )
