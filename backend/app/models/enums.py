"""Domain enumerations.

Terminology follows the client's own vocabulary as extracted in
``docs/ATTACHMENT_ANALYSIS.md`` — in particular WIP (Work In Progress) and
RIP (Report In Progress), which appear on both handwritten dashboard sheets.
"""

from __future__ import annotations

from enum import StrEnum


class CaseCategory(StrEnum):
    """Top-level split used by the sidebar and by case numbering."""

    INVESTIGATION = "INVESTIGATION"
    DEATH_CLAIM = "DEATH_CLAIM"


class CaseStatus(StrEnum):
    IMPORTED = "IMPORTED"
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    WIP = "WIP"
    FIELD_INVESTIGATION = "FIELD_INVESTIGATION"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    RIP = "RIP"
    REPORT_SUBMITTED = "REPORT_SUBMITTED"
    AWAITING_OFFICE_ASSIGNMENT = "AWAITING_OFFICE_ASSIGNMENT"
    OFFICE_PROCESSING = "OFFICE_PROCESSING"
    UNDER_REVIEW = "UNDER_REVIEW"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    VERIFIED = "VERIFIED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


#: Statuses that count as "open" work for TAT and workload purposes.
OPEN_STATUSES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.IMPORTED,
        CaseStatus.UNASSIGNED,
        CaseStatus.ASSIGNED,
        CaseStatus.ACCEPTED,
        CaseStatus.WIP,
        CaseStatus.FIELD_INVESTIGATION,
        CaseStatus.DOCUMENTS_PENDING,
        CaseStatus.RIP,
        CaseStatus.REPORT_SUBMITTED,
        CaseStatus.AWAITING_OFFICE_ASSIGNMENT,
        CaseStatus.OFFICE_PROCESSING,
        CaseStatus.UNDER_REVIEW,
        CaseStatus.CORRECTION_REQUIRED,
    }
)

#: Statuses that mean the case is finished, one way or another.
CLOSED_STATUSES: frozenset[CaseStatus] = frozenset(
    {CaseStatus.COMPLETED, CaseStatus.REJECTED, CaseStatus.CANCELLED}
)

#: "Work in progress" grouping for the dashboard WIP tile (Image 1 #3).
WIP_STATUSES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.ACCEPTED,
        CaseStatus.WIP,
        CaseStatus.FIELD_INVESTIGATION,
        CaseStatus.DOCUMENTS_PENDING,
    }
)

#: "Report in progress" grouping for the dashboard RIP tile (Image 1 #4).
RIP_STATUSES: frozenset[CaseStatus] = frozenset(
    {
        CaseStatus.RIP,
        CaseStatus.REPORT_SUBMITTED,
        CaseStatus.AWAITING_OFFICE_ASSIGNMENT,
        CaseStatus.OFFICE_PROCESSING,
        CaseStatus.UNDER_REVIEW,
        CaseStatus.CORRECTION_REQUIRED,
    }
)


class CaseOutcome(StrEnum):
    """The three outcomes drawn on both dashboard sheets."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    SUSPICIOUS = "SUSPICIOUS"


class ReportStatus(StrEnum):
    INTERIM = "INTERIM"
    FINAL = "FINAL"


class CasePriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TatState(StrEnum):
    IN_TAT = "IN_TAT"
    ABOUT_TO_BREACH = "ABOUT_TO_BREACH"
    OUT_OF_TAT = "OUT_OF_TAT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CompanyType(StrEnum):
    BANK = "BANK"
    INSURANCE = "INSURANCE"
    INVESTIGATION_CLIENT = "INVESTIGATION_CLIENT"
    OTHER = "OTHER"


class StaffCategory(StrEnum):
    """Image 1 distinguishes field investigators from back-office employees."""

    FIELD = "FIELD"
    BACK_OFFICE = "BACK_OFFICE"
    MANAGEMENT = "MANAGEMENT"


class EmploymentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PROBATION = "PROBATION"
    NOTICE_PERIOD = "NOTICE_PERIOD"
    RESIGNED = "RESIGNED"
    TERMINATED = "TERMINATED"
    ON_LEAVE = "ON_LEAVE"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    UNDISCLOSED = "UNDISCLOSED"


class FieldType(StrEnum):
    TEXT = "TEXT"
    TEXTAREA = "TEXTAREA"
    NUMBER = "NUMBER"
    CURRENCY = "CURRENCY"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIME = "TIME"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    SELECT = "SELECT"
    MULTI_SELECT = "MULTI_SELECT"
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    BOOLEAN = "BOOLEAN"
    YES_NO_NA = "YES_NO_NA"
    ADDRESS = "ADDRESS"
    FILE = "FILE"
    IMAGE = "IMAGE"
    SIGNATURE = "SIGNATURE"
    TABLE = "TABLE"
    HEADING = "HEADING"


class FieldSource(StrEnum):
    """Data provenance shown on the case detail screen."""

    BANK_SUPPLIED = "BANK_SUPPLIED"
    INVESTIGATION = "INVESTIGATION"
    SYSTEM = "SYSTEM"


class CaseFormStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    APPROVED = "APPROVED"


class ImportBatchStatus(StrEnum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    IMPORTING = "IMPORTING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ImportRowStatus(StrEnum):
    PENDING = "PENDING"
    VALID = "VALID"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DUPLICATE = "DUPLICATE"
    IMPORTED = "IMPORTED"
    SKIPPED = "SKIPPED"


class DocumentTemplateStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    #: Legacy binary .doc that must be re-saved as .docx before generation.
    NEEDS_CONVERSION = "NEEDS_CONVERSION"


class GeneratedFormat(StrEnum):
    DOCX = "DOCX"
    PDF = "PDF"


class DocumentCategory(StrEnum):
    KYC = "KYC"
    PHOTOGRAPH = "PHOTOGRAPH"
    MEDICAL = "MEDICAL"
    DEATH_CERTIFICATE = "DEATH_CERTIFICATE"
    FIR_PMR = "FIR_PMR"
    STATEMENT = "STATEMENT"
    INCOME_PROOF = "INCOME_PROOF"
    AGE_PROOF = "AGE_PROOF"
    REPORT = "REPORT"
    OTHER = "OTHER"


class NotificationType(StrEnum):
    CASE_ASSIGNED = "CASE_ASSIGNED"
    CASE_REASSIGNED = "CASE_REASSIGNED"
    DUE_DATE_APPROACHING = "DUE_DATE_APPROACHING"
    CASE_OVERDUE = "CASE_OVERDUE"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"
    CASE_APPROVED = "CASE_APPROVED"
    CASE_COMPLETED = "CASE_COMPLETED"
    IMPORT_COMPLETED = "IMPORT_COMPLETED"
    SYSTEM = "SYSTEM"


class AuditAction(StrEnum):
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    CASE_CREATED = "CASE_CREATED"
    CASE_IMPORTED = "CASE_IMPORTED"
    CASE_UPDATED = "CASE_UPDATED"
    CASE_ASSIGNED = "CASE_ASSIGNED"
    CASE_REASSIGNED = "CASE_REASSIGNED"
    CASE_STATUS_CHANGED = "CASE_STATUS_CHANGED"
    CASE_DELETED = "CASE_DELETED"
    CASE_SUBMITTED_TO_OFFICE = "CASE_SUBMITTED_TO_OFFICE"
    CASE_OFFICE_ASSIGNED = "CASE_OFFICE_ASSIGNED"
    CASE_OFFICE_REASSIGNED = "CASE_OFFICE_REASSIGNED"
    LOCKED_FIELD_EDITED = "LOCKED_FIELD_EDITED"
    FIELD_UNLOCKED = "FIELD_UNLOCKED"
    FIELD_RELOCKED = "FIELD_RELOCKED"
    FORM_UPDATED = "FORM_UPDATED"
    FORM_SUBMITTED = "FORM_SUBMITTED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"
    DOCUMENT_GENERATED = "DOCUMENT_GENERATED"
    IMPORT_CREATED = "IMPORT_CREATED"
    IMPORT_COMMITTED = "IMPORT_COMMITTED"
    IMPORT_ROLLED_BACK = "IMPORT_ROLLED_BACK"
    STAFF_CREATED = "STAFF_CREATED"
    STAFF_UPDATED = "STAFF_UPDATED"
    STAFF_DISABLED = "STAFF_DISABLED"
    CLOCK_IN = "CLOCK_IN"
    CLOCK_OUT = "CLOCK_OUT"
    ATTENDANCE_EDITED = "ATTENDANCE_EDITED"
    ROLE_CHANGED = "ROLE_CHANGED"
    PERMISSION_CHANGED = "PERMISSION_CHANGED"
    SETTINGS_CHANGED = "SETTINGS_CHANGED"
    COMPANY_CHANGED = "COMPANY_CHANGED"
    TEMPLATE_CHANGED = "TEMPLATE_CHANGED"
    EXPORT_RUN = "EXPORT_RUN"
    DATA_PURGED = "DATA_PURGED"


class AttendanceStatus(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    HALF_DAY = "HALF_DAY"
    WEEK_OFF = "WEEK_OFF"
    HOLIDAY = "HOLIDAY"
    ON_LEAVE = "ON_LEAVE"
    FIELD_DUTY = "FIELD_DUTY"


class LeaveType(StrEnum):
    CASUAL = "CASUAL"
    SICK = "SICK"
    EARNED = "EARNED"
    UNPAID = "UNPAID"
    MATERNITY = "MATERNITY"
    PATERNITY = "PATERNITY"
    COMPENSATORY = "COMPENSATORY"


class LeaveStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AssignmentStage(StrEnum):
    """The operational stage an assignment belongs to.

    A case is worked twice: once in the field, once in the office. Both
    assignments live side by side rather than one overwriting the other.
    """

    FIELD_INVESTIGATION = "FIELD_INVESTIGATION"
    OFFICE_PROCESSING = "OFFICE_PROCESSING"
    REVIEW = "REVIEW"


class AssignmentState(StrEnum):
    """Lifecycle of a single assignment row."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"


class VisitStatus(StrEnum):
    """Field-visit progress, tracked separately from the case status."""

    NOT_STARTED = "NOT_STARTED"
    VISIT_SCHEDULED = "VISIT_SCHEDULED"
    VISIT_IN_PROGRESS = "VISIT_IN_PROGRESS"
    VISITED = "VISITED"
    INFORMATION_COLLECTED = "INFORMATION_COLLECTED"
    FORM_COMPLETED = "FORM_COMPLETED"
    SUBMITTED_TO_OFFICE = "SUBMITTED_TO_OFFICE"


class ClockState(StrEnum):
    """Attendance state — deliberately distinct from online/offline."""

    CLOCKED_IN = "CLOCKED_IN"
    CLOCKED_OUT = "CLOCKED_OUT"


class ActivityAction(StrEnum):
    """What a user did inside the application.

    Feeds the Super Admin's User Activity Log. This is the operational trail —
    ``AuditAction`` remains the compliance record of data changes.
    """

    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    CLOCK_IN = "CLOCK_IN"
    CLOCK_OUT = "CLOCK_OUT"
    HEARTBEAT = "HEARTBEAT"
    PAGE_VIEW = "PAGE_VIEW"
    CASE_OPENED = "CASE_OPENED"
    CASE_CREATED = "CASE_CREATED"
    CASE_EDITED = "CASE_EDITED"
    CASE_ASSIGNED = "CASE_ASSIGNED"
    STATUS_CHANGED = "STATUS_CHANGED"
    FORM_OPENED = "FORM_OPENED"
    FORM_SAVED = "FORM_SAVED"
    FORM_SUBMITTED = "FORM_SUBMITTED"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"
    CASE_APPROVED = "CASE_APPROVED"
    CASE_COMPLETED = "CASE_COMPLETED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"
    DOCUMENT_GENERATED = "DOCUMENT_GENERATED"
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED"
    EXPORT_RUN = "EXPORT_RUN"
    IMPORT_RUN = "IMPORT_RUN"
    FIELD_UNLOCKED = "FIELD_UNLOCKED"
    NOTE_ADDED = "NOTE_ADDED"


#: Grouping used by the activity-log filter dropdown.
ACTIVITY_MODULES: dict[ActivityAction, str] = {
    ActivityAction.LOGIN: "Authentication",
    ActivityAction.LOGOUT: "Authentication",
    ActivityAction.CLOCK_IN: "Attendance",
    ActivityAction.CLOCK_OUT: "Attendance",
    ActivityAction.HEARTBEAT: "Session",
    ActivityAction.PAGE_VIEW: "Session",
    ActivityAction.CASE_OPENED: "Cases",
    ActivityAction.CASE_CREATED: "Cases",
    ActivityAction.CASE_EDITED: "Cases",
    ActivityAction.CASE_ASSIGNED: "Cases",
    ActivityAction.STATUS_CHANGED: "Cases",
    ActivityAction.FORM_OPENED: "Forms",
    ActivityAction.FORM_SAVED: "Forms",
    ActivityAction.FORM_SUBMITTED: "Forms",
    ActivityAction.CORRECTION_REQUESTED: "Review",
    ActivityAction.CASE_APPROVED: "Review",
    ActivityAction.CASE_COMPLETED: "Review",
    ActivityAction.DOCUMENT_UPLOADED: "Documents",
    ActivityAction.DOCUMENT_DELETED: "Documents",
    ActivityAction.DOCUMENT_GENERATED: "Documents",
    ActivityAction.DOCUMENT_DOWNLOADED: "Documents",
    ActivityAction.EXPORT_RUN: "Reports",
    ActivityAction.IMPORT_RUN: "Import",
    ActivityAction.FIELD_UNLOCKED: "Cases",
    ActivityAction.NOTE_ADDED: "Cases",
}
