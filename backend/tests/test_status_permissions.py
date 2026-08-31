"""Who is allowed to move a case into which status.

The status endpoint used to ask only for ``case.view``. Anyone who could open
a case could also drive it to Completed, skipping the office stage, the review
and the quality check — the whole point of the workflow. These tests pin the
rule to the roles as they are actually seeded, so a change to either the roles
or the status map has to be made deliberately.
"""

from __future__ import annotations

import pytest

from app.core.permissions import ROLES
from app.models.enums import CaseStatus
from app.services.case_workflow import STATUS_PERMISSIONS, may_set_status

ROLE_PERMISSIONS = {role.code: frozenset(role.permissions) for role in ROLES}


def allowed(role: str, target: CaseStatus, **kwargs: bool) -> bool:
    return may_set_status(
        target, permission_codes=ROLE_PERMISSIONS[role], **kwargs
    )


class TestInvestigator:
    """A field investigator owns their own case only up to submission."""

    @pytest.mark.parametrize(
        "target",
        [
            CaseStatus.WIP,
            CaseStatus.FIELD_INVESTIGATION,
            CaseStatus.DOCUMENTS_PENDING,
            CaseStatus.RIP,
            CaseStatus.REPORT_SUBMITTED,
        ],
    )
    def test_may_work_and_submit_own_case(self, target: CaseStatus) -> None:
        assert allowed("INVESTIGATOR", target, is_assignee=True)

    @pytest.mark.parametrize(
        "target",
        [
            CaseStatus.UNDER_REVIEW,
            CaseStatus.QUALITY_CHECK,
            CaseStatus.VERIFIED,
            CaseStatus.COMPLETED,
            CaseStatus.REJECTED,
        ],
    )
    def test_cannot_close_out_own_case(self, target: CaseStatus) -> None:
        """The hole this file exists for: no self-completion."""
        assert not allowed("INVESTIGATOR", target, is_assignee=True)

    def test_cannot_work_somebody_elses_case(self) -> None:
        assert not allowed("INVESTIGATOR", CaseStatus.WIP)

    def test_cannot_assign(self) -> None:
        assert not allowed("INVESTIGATOR", CaseStatus.ASSIGNED, is_assignee=True)


class TestOfficeStaff:
    def test_may_hand_the_report_back_for_review(self) -> None:
        assert allowed("OFFICE_STAFF", CaseStatus.UNDER_REVIEW)

    def test_may_process_in_the_office(self) -> None:
        assert allowed("OFFICE_STAFF", CaseStatus.OFFICE_PROCESSING)

    def test_cannot_verify_or_complete(self) -> None:
        assert not allowed("OFFICE_STAFF", CaseStatus.VERIFIED)
        assert not allowed("OFFICE_STAFF", CaseStatus.COMPLETED)

    def test_cannot_send_to_quality_check(self) -> None:
        """Quality check is the reviewer's call, not the preparer's."""
        assert not allowed("OFFICE_STAFF", CaseStatus.QUALITY_CHECK)


class TestReviewer:
    def test_may_review_quality_check_and_complete(self) -> None:
        for target in (
            CaseStatus.QUALITY_CHECK,
            CaseStatus.VERIFIED,
            CaseStatus.CORRECTION_REQUIRED,
            CaseStatus.COMPLETED,
        ):
            assert allowed("REVIEWER", target), target

    def test_cannot_cancel(self) -> None:
        assert not allowed("REVIEWER", CaseStatus.CANCELLED)


class TestSuperAdmin:
    def test_may_set_anything(self) -> None:
        for target in CaseStatus:
            assert may_set_status(
                target, permission_codes=frozenset(), is_super_admin=True
            ), target


class TestCoverage:
    def test_every_status_has_a_rule(self) -> None:
        """A status with no entry would fall through to 'nobody may set it'."""
        missing = [s.value for s in CaseStatus if s not in STATUS_PERMISSIONS]
        assert not missing, f"No permission rule for: {missing}"

    def test_no_status_is_open_to_bare_case_view(self) -> None:
        """``case.view`` alone must not move a case anywhere."""
        for target in CaseStatus:
            assert not may_set_status(
                target, permission_codes=frozenset({"case.view"})
            ), target
