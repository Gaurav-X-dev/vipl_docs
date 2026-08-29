"""Model package. Importing this module registers every table on ``Base``."""

from app.db.base_class import Base
from app.models.audit import AuditLog, CaseTimelineEvent, UserActivity
from app.models.case import (
    Case,
    CaseAssignment,
    CaseDocument,
    CaseNote,
    CaseNumberSequence,
    CaseStatusHistory,
    DeathClaimDetail,
)
from app.models.company import CaseType, Company
from app.models.document import DocumentTemplate, GeneratedDocument
from app.models.form import (
    CaseFieldValue,
    CaseFieldValueHistory,
    CaseForm,
    FormField,
    FormSection,
    FormTemplate,
)
from app.models.hr import (
    Attendance,
    AttendanceSession,
    Department,
    Designation,
    Employee,
    LeaveRecord,
)
from app.models.importing import (
    ImportBatch,
    ImportColumnMapping,
    ImportRow,
    ImportTemplate,
)
from app.models.misc import AppSetting, Notification, SavedFilter
from app.models.rbac import Permission, Role, role_permissions, user_roles
from app.models.user import LoginAttempt, User, UserSession

__all__ = [
    "AppSetting",
    "Attendance",
    "AttendanceSession",
    "AuditLog",
    "Base",
    "Case",
    "CaseAssignment",
    "CaseDocument",
    "CaseFieldValue",
    "CaseFieldValueHistory",
    "CaseForm",
    "CaseNote",
    "CaseNumberSequence",
    "CaseStatusHistory",
    "CaseTimelineEvent",
    "CaseType",
    "Company",
    "DeathClaimDetail",
    "Department",
    "Designation",
    "DocumentTemplate",
    "Employee",
    "FormField",
    "FormSection",
    "FormTemplate",
    "GeneratedDocument",
    "ImportBatch",
    "ImportColumnMapping",
    "ImportRow",
    "ImportTemplate",
    "LeaveRecord",
    "LoginAttempt",
    "Notification",
    "Permission",
    "Role",
    "SavedFilter",
    "User",
    "UserActivity",
    "UserSession",
    "role_permissions",
    "user_roles",
]
