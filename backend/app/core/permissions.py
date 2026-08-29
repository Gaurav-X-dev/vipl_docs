"""Canonical permission catalogue and the default role -> permission matrix.

Permissions live in the database (``permissions`` / ``role_permissions``) so an
administrator can re-wire them at runtime. This module is the *seed* definition
and the single place where permission codes are spelled out for the backend.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    code: str
    module: str
    description: str


PERMISSIONS: tuple[PermissionDef, ...] = (
    # Dashboard
    PermissionDef("dashboard.view", "Dashboard", "View the dashboard"),
    PermissionDef("dashboard.view_all", "Dashboard", "See organisation-wide figures"),
    # Cases (shared across investigation + death claim)
    PermissionDef("case.view", "Cases", "View cases"),
    PermissionDef("case.view_all", "Cases", "View every case, not only assigned ones"),
    PermissionDef("case.create", "Cases", "Create cases manually"),
    PermissionDef("case.edit", "Cases", "Edit case header information"),
    PermissionDef("case.assign", "Cases", "Assign a case to an investigator"),
    PermissionDef("case.reassign", "Cases", "Reassign an already assigned case"),
    PermissionDef("case.assign_office", "Cases", "Assign a submitted case to office staff"),
    PermissionDef("case.process_office", "Cases", "Work a case in the back-office stage"),
    PermissionDef("case.complete", "Cases", "Mark a case completed"),
    PermissionDef("case.review", "Cases", "Approve or return a submitted case"),
    PermissionDef("case.export", "Cases", "Export cases to Excel/CSV"),
    PermissionDef("case.delete", "Cases", "Cancel or delete a case"),
    # Investigation
    PermissionDef("investigation.view", "Investigation", "View investigation cases"),
    PermissionDef("investigation.edit", "Investigation", "Fill the investigation form"),
    PermissionDef("investigation.assign", "Investigation", "Assign investigation cases"),
    # Death claim
    PermissionDef("death_claim.view", "Death Claims", "View death claim cases"),
    PermissionDef("death_claim.edit", "Death Claims", "Fill the death claim form"),
    PermissionDef("death_claim.assign", "Death Claims", "Assign death claim cases"),
    # Documents
    PermissionDef("document.upload", "Documents", "Upload evidence to a case"),
    PermissionDef("document.delete", "Documents", "Delete case evidence"),
    PermissionDef("document.generate", "Documents", "Generate the client DOCX/PDF"),
    # Import
    PermissionDef("import.create", "Import", "Upload and run an Excel/CSV import"),
    PermissionDef("import.view", "Import", "View import batches and results"),
    PermissionDef("import.rollback", "Import", "Roll an import batch back"),
    # Attendance
    PermissionDef("attendance.self", "Attendance", "Clock in and out"),
    PermissionDef("attendance.view_all", "Attendance", "See everyone's attendance"),
    PermissionDef("attendance.manage", "Attendance", "Correct attendance records"),
    # Activity
    PermissionDef("activity.view_self", "Activity", "See your own activity log"),
    PermissionDef("activity.view_all", "Activity", "See every user's activity log"),
    # Staff
    PermissionDef("staff.view", "Staff", "View staff"),
    PermissionDef("staff.create", "Staff", "Create staff"),
    PermissionDef("staff.edit", "Staff", "Edit staff"),
    PermissionDef("staff.disable", "Staff", "Enable/disable a staff login"),
    # HR
    PermissionDef("hr.view", "HR", "View HR records"),
    PermissionDef("hr.manage", "HR", "Manage HR records"),
    # Companies / templates
    PermissionDef("company.view", "Companies", "View companies and clients"),
    PermissionDef("company.manage", "Companies", "Create/edit companies and clients"),
    PermissionDef("template.view", "Templates", "View form and document templates"),
    PermissionDef("template.manage", "Templates", "Create/edit templates and mappings"),
    # Reports
    PermissionDef("reports.view", "Reports", "View reports"),
    PermissionDef("reports.export", "Reports", "Export reports"),
    # Audit
    PermissionDef("audit.view", "Audit", "View audit logs"),
    # Administration
    PermissionDef("users.manage", "Administration", "Manage user accounts"),
    PermissionDef("roles.manage", "Administration", "Manage roles and permissions"),
    PermissionDef("settings.manage", "Administration", "Manage application settings"),
)

ALL_PERMISSION_CODES: tuple[str, ...] = tuple(p.code for p in PERMISSIONS)


@dataclass(frozen=True)
class RoleDef:
    code: str
    name: str
    description: str
    is_system: bool
    permissions: tuple[str, ...]


_MANAGER_PERMS = (
    "dashboard.view",
    "dashboard.view_all",
    "case.view",
    "case.view_all",
    "case.create",
    "case.edit",
    "case.assign",
    "case.reassign",
    "case.assign_office",
    "case.process_office",
    "case.complete",
    "case.review",
    "case.export",
    "investigation.view",
    "investigation.edit",
    "investigation.assign",
    "death_claim.view",
    "death_claim.edit",
    "death_claim.assign",
    "document.upload",
    "document.generate",
    "import.create",
    "import.view",
    "staff.view",
    "company.view",
    "template.view",
    "reports.view",
    "reports.export",
    "audit.view",
    "attendance.self",
    "attendance.view_all",
    "activity.view_self",
    "activity.view_all",
)

_ADMIN_PERMS = _MANAGER_PERMS + (
    "case.delete",
    "document.delete",
    "import.rollback",
    "staff.create",
    "staff.edit",
    "staff.disable",
    "hr.view",
    "hr.manage",
    "company.manage",
    "template.manage",
    "users.manage",
    "settings.manage",
    "attendance.manage",
)

_INVESTIGATOR_PERMS = (
    "dashboard.view",
    "case.view",
    "investigation.view",
    "investigation.edit",
    "death_claim.view",
    "death_claim.edit",
    "document.upload",
    "document.generate",
    "attendance.self",
    "activity.view_self",
)

_REVIEWER_PERMS = (
    "dashboard.view",
    "dashboard.view_all",
    "case.view",
    "case.view_all",
    "case.review",
    "case.complete",
    "case.export",
    "investigation.view",
    "death_claim.view",
    "document.generate",
    "reports.view",
    "reports.export",
    "audit.view",
    "case.process_office",
    "attendance.self",
    "activity.view_self",
)

_HR_PERMS = (
    "dashboard.view",
    "staff.view",
    "staff.create",
    "staff.edit",
    "hr.view",
    "hr.manage",
    "reports.view",
    "attendance.self",
    "attendance.view_all",
    "attendance.manage",
    "activity.view_self",
)

_DATA_ENTRY_PERMS = (
    "dashboard.view",
    "case.view",
    "case.view_all",
    "case.create",
    "case.edit",
    "investigation.view",
    "investigation.edit",
    "death_claim.view",
    "death_claim.edit",
    "document.upload",
    "import.create",
    "import.view",
    "company.view",
    "template.view",
    "case.process_office",
    "attendance.self",
    "activity.view_self",
)

_OFFICE_STAFF_PERMS = (
    "dashboard.view",
    "case.view",
    "case.view_all",
    "case.edit",
    "case.process_office",
    "case.export",
    "investigation.view",
    "investigation.edit",
    "death_claim.view",
    "death_claim.edit",
    "document.upload",
    "document.generate",
    "company.view",
    "template.view",
    "reports.view",
    "attendance.self",
    "activity.view_self",
)

ROLES: tuple[RoleDef, ...] = (
    RoleDef(
        "SUPER_ADMIN",
        "Super Admin",
        "Unrestricted access to every module and setting.",
        True,
        ALL_PERMISSION_CODES,
    ),
    RoleDef(
        "ADMIN",
        "Admin",
        "Full operational access including staff, templates and settings.",
        True,
        _ADMIN_PERMS,
    ),
    RoleDef(
        "MANAGER",
        "Manager",
        "Runs the case pipeline: assignment, review and reporting.",
        True,
        _MANAGER_PERMS,
    ),
    RoleDef(
        "INVESTIGATOR",
        "Investigator",
        "Field investigator. Sees only the cases assigned to them.",
        True,
        _INVESTIGATOR_PERMS,
    ),
    RoleDef(
        "OFFICE_STAFF",
        "Office Staff",
        "Back-office processing of cases submitted by field investigators.",
        True,
        _OFFICE_STAFF_PERMS,
    ),
    RoleDef(
        "REVIEWER",
        "Reviewer",
        "Quality check on submitted reports before completion.",
        True,
        _REVIEWER_PERMS,
    ),
    RoleDef(
        "HR",
        "HR",
        "Employee, attendance and leave administration.",
        True,
        _HR_PERMS,
    ),
    RoleDef(
        "DATA_ENTRY",
        "Data Entry Operator",
        "Back-office data entry and daily Excel import.",
        True,
        _DATA_ENTRY_PERMS,
    ),
)

SUPER_ADMIN_ROLE_CODE = "SUPER_ADMIN"
INVESTIGATOR_ROLE_CODE = "INVESTIGATOR"
OFFICE_STAFF_ROLE_CODE = "OFFICE_STAFF"
