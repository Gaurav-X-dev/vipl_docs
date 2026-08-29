"""Idempotent seeding of every master record the application needs to run.

Safe to re-run: existing rows are updated in place, never duplicated. The Super
Admin is created only if it does not already exist, and its password comes from
the environment — never from source.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import PROJECT_ROOT, settings
from app.core.permissions import PERMISSIONS, ROLES, SUPER_ADMIN_ROLE_CODE
from app.core.security import hash_password
from app.documents import docx_renderer
from app.models.company import CaseType, Company
from app.models.document import DocumentTemplate
from app.models.enums import DocumentTemplateStatus, StaffCategory
from app.models.form import FormField, FormSection, FormTemplate
from app.models.hr import Department, Designation, Employee
from app.models.importing import ImportColumnMapping, ImportTemplate
from app.models.rbac import Permission, Role
from app.models.user import User
from app.seeds import catalogue
from app.seeds.form_dsl import T
from app.seeds.forms_death_claim import DEATH_CLAIM_TEMPLATES
from app.seeds.forms_investigation import HDFC_PROFILE_CHECK, INVESTIGATION_TEMPLATES
from app.services import settings_service
from app.utils.dates import utcnow
from app.utils.files import relative_to_storage, sha256_bytes

logger = logging.getLogger("app.seed")


@dataclass
class SeedReport:
    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def add(self, bucket: str, key: str, count: int = 1) -> None:
        target = self.created if bucket == "created" else self.updated
        target[key] = target.get(key, 0) + count

    def as_lines(self) -> list[str]:
        lines = ["Seed summary", "-" * 60]
        for label, data in (("Created", self.created), ("Updated", self.updated)):
            if data:
                lines.append(f"{label}:")
                for key in sorted(data):
                    lines.append(f"    {data[key]:>4}  {key}")
        lines.extend(self.notes)
        return lines


# --------------------------------------------------------------------------- #
# RBAC
# --------------------------------------------------------------------------- #
async def seed_permissions(session: AsyncSession, report: SeedReport) -> dict[str, Permission]:
    existing = {
        row.code: row for row in (await session.execute(select(Permission))).scalars().all()
    }
    for definition in PERMISSIONS:
        row = existing.get(definition.code)
        if row is None:
            row = Permission(
                code=definition.code,
                module=definition.module,
                description=definition.description,
            )
            session.add(row)
            existing[definition.code] = row
            report.add("created", "permissions")
        elif row.description != definition.description or row.module != definition.module:
            row.module = definition.module
            row.description = definition.description
            report.add("updated", "permissions")
    await session.flush()
    return existing


async def seed_roles(
    session: AsyncSession, permissions: dict[str, Permission], report: SeedReport
) -> dict[str, Role]:
    result = await session.execute(select(Role).options(selectinload(Role.permissions)))
    existing = {row.code: row for row in result.unique().scalars().all()}

    for definition in ROLES:
        row = existing.get(definition.code)
        wanted = [permissions[code] for code in definition.permissions if code in permissions]
        if row is None:
            row = Role(
                code=definition.code,
                name=definition.name,
                description=definition.description,
                is_system=definition.is_system,
                is_active=True,
                permissions=wanted,
            )
            session.add(row)
            existing[definition.code] = row
            report.add("created", "roles")
        else:
            row.name = definition.name
            row.description = definition.description
            row.is_system = definition.is_system
            # System roles keep their permission matrix in sync with the code.
            if row.is_system and row.permission_codes != set(definition.permissions):
                row.permissions = wanted
                report.add("updated", "roles")
    await session.flush()
    return existing


async def seed_super_admin(
    session: AsyncSession, roles: dict[str, Role], report: SeedReport
) -> User:
    email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    result = await session.execute(
        select(User).options(selectinload(User.roles)).where(func.lower(User.email) == email)
    )
    user = result.unique().scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(settings.SUPER_ADMIN_PASSWORD),
            full_name=settings.SUPER_ADMIN_NAME,
            staff_category=StaffCategory.MANAGEMENT,
            is_active=True,
            login_enabled=True,
            is_super_admin=True,
            must_change_password=False,
            password_changed_at=utcnow(),
        )
        super_role = roles.get(SUPER_ADMIN_ROLE_CODE)
        if super_role is not None:
            user.roles = [super_role]
        session.add(user)
        await session.flush()
        report.add("created", "super admin")
        report.notes.append(
            f"\nSuper Admin created: {email}\n"
            "  Password comes from SUPER_ADMIN_PASSWORD in backend/.env — "
            "change it before production."
        )
    else:
        # Never reset an existing password; only guarantee the flags.
        if not user.is_super_admin or not user.is_active or not user.login_enabled:
            user.is_super_admin = True
            user.is_active = True
            user.login_enabled = True
            report.add("updated", "super admin")
        super_role = roles.get(SUPER_ADMIN_ROLE_CODE)
        if super_role is not None and super_role.code not in user.role_codes:
            user.roles = list(user.roles) + [super_role]

    # Query explicitly: a freshly flushed User has no loaded relationships.
    linked_employee = (
        await session.execute(select(Employee).where(Employee.user_id == user.id))
    ).scalar_one_or_none()
    if linked_employee is None:
        existing_employee = (
            await session.execute(select(Employee).where(Employee.employee_code == "EMP0001"))
        ).scalar_one_or_none()
        if existing_employee is None:
            session.add(
                Employee(
                    employee_code="EMP0001",
                    user_id=user.id,
                    first_name=settings.SUPER_ADMIN_NAME.split(" ")[0] or "Super",
                    last_name=" ".join(settings.SUPER_ADMIN_NAME.split(" ")[1:]) or "Administrator",
                    email=email,
                    staff_category=StaffCategory.MANAGEMENT,
                    joining_date=utcnow().date(),
                )
            )
            report.add("created", "employee profiles")
    return user


# --------------------------------------------------------------------------- #
# HR masters, companies and case types
# --------------------------------------------------------------------------- #
async def seed_hr_masters(session: AsyncSession, report: SeedReport) -> None:
    existing_departments = {
        row.code for row in (await session.execute(select(Department))).scalars().all()
    }
    for code, name in catalogue.DEPARTMENTS:
        if code not in existing_departments:
            session.add(Department(code=code, name=name))
            report.add("created", "departments")

    existing_designations = {
        row.code for row in (await session.execute(select(Designation))).scalars().all()
    }
    for code, name, grade in catalogue.DESIGNATIONS:
        if code not in existing_designations:
            session.add(Designation(code=code, name=name, grade=grade))
            report.add("created", "designations")
    await session.flush()


async def seed_companies(session: AsyncSession, report: SeedReport) -> dict[str, Company]:
    existing = {row.code: row for row in (await session.execute(select(Company))).scalars().all()}
    for definition in catalogue.COMPANIES:
        aliases = "|".join(definition.aliases)
        row = existing.get(definition.code)
        if row is None:
            row = Company(
                code=definition.code,
                name=definition.name,
                short_name=definition.short_name,
                company_type=definition.company_type,
                import_aliases=aliases,
                default_tat_days=definition.default_tat_days,
                is_active=True,
            )
            session.add(row)
            existing[definition.code] = row
            report.add("created", "companies")
        elif row.import_aliases != aliases or row.name != definition.name:
            row.name = definition.name
            row.short_name = definition.short_name
            row.import_aliases = aliases
            report.add("updated", "companies")
    await session.flush()
    return existing


async def seed_case_types(session: AsyncSession, report: SeedReport) -> dict[str, CaseType]:
    existing = {row.code: row for row in (await session.execute(select(CaseType))).scalars().all()}
    for definition in catalogue.CASE_TYPES:
        aliases = "|".join(definition.aliases)
        row = existing.get(definition.code)
        if row is None:
            row = CaseType(
                code=definition.code,
                name=definition.name,
                category=definition.category,
                description=definition.description,
                import_aliases=aliases,
                default_tat_days=definition.default_tat_days,
                display_order=definition.display_order,
                is_active=True,
            )
            session.add(row)
            existing[definition.code] = row
            report.add("created", "case types")
        elif row.import_aliases != aliases or row.name != definition.name:
            row.name = definition.name
            row.description = definition.description
            row.import_aliases = aliases
            row.default_tat_days = definition.default_tat_days
            report.add("updated", "case types")
    await session.flush()
    return existing


# --------------------------------------------------------------------------- #
# Import template
# --------------------------------------------------------------------------- #
async def seed_import_template(session: AsyncSession, report: SeedReport) -> ImportTemplate:
    result = await session.execute(
        select(ImportTemplate)
        .options(selectinload(ImportTemplate.mappings))
        .where(ImportTemplate.code == catalogue.IMPORT_TEMPLATE_CODE)
    )
    template = result.unique().scalar_one_or_none()

    if template is None:
        template = ImportTemplate(
            code=catalogue.IMPORT_TEMPLATE_CODE,
            name=catalogue.IMPORT_TEMPLATE_NAME,
            description=catalogue.IMPORT_TEMPLATE_DESCRIPTION,
            header_row=1,
            duplicate_key_fields=catalogue.DUPLICATE_KEY,
            fallback_duplicate_key_fields=catalogue.FALLBACK_DUPLICATE_KEY,
            is_default=True,
            is_active=True,
        )
        session.add(template)
        await session.flush()
        report.add("created", "import templates")
        # A newly-created relationship is not loaded by the SELECT above.
        # Accessing ``template.mappings`` here would trigger implicit database
        # I/O, which AsyncSession intentionally forbids (MissingGreenlet).
        existing: dict[str, ImportColumnMapping] = {}
    else:
        template.duplicate_key_fields = catalogue.DUPLICATE_KEY
        template.fallback_duplicate_key_fields = catalogue.FALLBACK_DUPLICATE_KEY
        template.is_default = True
        existing = {row.target_field: row for row in template.mappings}

    for order, column in enumerate(catalogue.IMPORT_COLUMNS):
        aliases = "|".join(column.aliases)
        row = existing.get(column.target_field)
        if row is None:
            session.add(
                ImportColumnMapping(
                    template_id=template.id,
                    source_column=column.source_column,
                    source_aliases=aliases or None,
                    target_field=column.target_field,
                    data_type=column.data_type,
                    is_required=column.is_required,
                    display_order=order,
                    notes=column.notes or None,
                )
            )
            report.add("created", "import column mappings")
        else:
            row.source_column = column.source_column
            row.source_aliases = aliases or None
            row.data_type = column.data_type
            row.is_required = column.is_required
            row.display_order = order
    await session.flush()
    return template


# --------------------------------------------------------------------------- #
# Form templates
# --------------------------------------------------------------------------- #
def _all_form_templates() -> tuple[T, ...]:
    # HDFC's pre-claim source file is a legacy binary .doc that cannot be read,
    # so its layout reuses the HDFC profile-check structure until a .docx arrives.
    hdfc_pre_claim = T(
        code="HDFC_PRE_CLAIM",
        name="HDFC Life — Pre Claim Report",
        company="HDFC",
        case_type="PRE_CLAIM",
        source_document="investigation_docs/HDFC Pre claim.doc",
        description=(
            "The supplied HDFC pre-claim file is a legacy Word 97-2003 binary .doc "
            "and could not be parsed. This layout mirrors the HDFC pre-claims "
            "profile-check form; replace it once a .docx version is provided."
        ),
        sections=HDFC_PROFILE_CHECK.sections,
    )
    return INVESTIGATION_TEMPLATES + (hdfc_pre_claim,) + DEATH_CLAIM_TEMPLATES


async def seed_form_templates(
    session: AsyncSession,
    companies: dict[str, Company],
    case_types: dict[str, CaseType],
    report: SeedReport,
) -> None:
    for definition in _all_form_templates():
        company = companies.get(definition.company)
        case_type = case_types.get(definition.case_type)
        if company is None or case_type is None:
            report.notes.append(
                f"  ! skipped form template {definition.code}: unknown company or case type"
            )
            continue

        existing = (
            (
                await session.execute(
                    select(FormTemplate).where(
                        FormTemplate.company_id == company.id,
                        FormTemplate.case_type_id == case_type.id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            continue  # never rewrite a version that live cases may be using

        template = FormTemplate(
            code=definition.code,
            name=definition.name,
            company_id=company.id,
            case_type_id=case_type.id,
            version=1,
            is_active=True,
            description=definition.description,
            source_document=definition.source_document,
        )
        session.add(template)
        await session.flush()

        # Field keys must be unique across the whole template, not just within
        # a section. Answers are stored per key, so two fields sharing one key
        # are one answer wearing two hats: typing in either changes both.
        # Several client forms ask the same thing twice (a summary near the top
        # and again in the Conclusion), so the first — the one written into the
        # insurer's own layout — wins and the repeat is dropped.
        seen: set[str] = set()
        for section_order, section_def in enumerate(definition.sections):
            section = FormSection(
                template_id=template.id,
                key=section_def.key,
                title=section_def.title,
                description=section_def.description,
                display_order=section_order,
                is_repeatable=section_def.repeatable,
            )
            session.add(section)
            await session.flush()
            for field_order, field_def in enumerate(section_def.fields):
                if field_def.key in seen:
                    report.notes.append(
                        f"  · {definition.code}: dropped repeat of "
                        f"'{field_def.key}' in section '{section_def.key}'"
                    )
                    continue
                seen.add(field_def.key)
                session.add(FormField(section_id=section.id, **field_def.as_kwargs(field_order)))
        report.add("created", "form templates")
    await session.flush()


# --------------------------------------------------------------------------- #
# Document templates
# --------------------------------------------------------------------------- #
async def seed_document_templates(
    session: AsyncSession,
    companies: dict[str, Company],
    case_types: dict[str, CaseType],
    report: SeedReport,
) -> None:
    settings.ensure_storage_dirs()

    for definition in catalogue.DOCUMENT_TEMPLATES:
        company = companies.get(definition.company_code)
        case_type = case_types.get(definition.case_type_code)
        if company is None or case_type is None:
            continue

        source = PROJECT_ROOT / definition.folder / definition.filename
        if not source.exists():
            report.notes.append(f"  ! missing source document: {source.name}")
            continue

        existing = (
            (
                await session.execute(
                    select(DocumentTemplate).where(
                        DocumentTemplate.company_id == company.id,
                        DocumentTemplate.case_type_id == case_type.id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            continue

        payload = source.read_bytes()
        is_docx = payload.startswith(b"PK\x03\x04")
        stored_name = f"{company.code}_{case_type.code}_v1{source.suffix.lower()}"
        original_path = settings.template_originals_dir / stored_name
        shutil.copy2(source, original_path)

        tagged_relative: str | None = None
        placeholders: dict[str, str] = {}
        if is_docx:
            found = docx_renderer.list_placeholders(original_path)
            if found:
                tagged_path = settings.template_tagged_dir / stored_name
                shutil.copy2(original_path, tagged_path)
                tagged_relative = relative_to_storage(tagged_path)
                placeholders = dict.fromkeys(found, "")

        session.add(
            DocumentTemplate(
                code=f"{company.code}_{case_type.code}",
                name=definition.name,
                company_id=company.id,
                case_type_id=case_type.id,
                version=1,
                status=(
                    DocumentTemplateStatus.ACTIVE
                    if is_docx
                    else DocumentTemplateStatus.NEEDS_CONVERSION
                ),
                original_filename=definition.filename,
                original_path=relative_to_storage(original_path),
                tagged_path=tagged_relative,
                checksum_sha256=sha256_bytes(payload),
                size_bytes=len(payload),
                placeholder_map=placeholders or None,
                notes=definition.notes or None,
            )
        )
        report.add("created", "document templates")
        if not is_docx:
            report.notes.append(
                f"  ! {definition.filename} is a legacy binary .doc — registered as "
                "NEEDS_CONVERSION; PDF generation still works."
            )
        elif not tagged_relative:
            report.notes.append(
                f"  - {definition.filename} has no placeholders yet; run "
                "scripts/tag_templates.py to produce the tagged copy."
            )
    await session.flush()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
async def seed_all(session: AsyncSession) -> SeedReport:
    report = SeedReport()

    created_settings = await settings_service.ensure_defaults(session)
    if created_settings:
        report.add("created", "settings", created_settings)

    permissions = await seed_permissions(session, report)
    roles = await seed_roles(session, permissions, report)
    await seed_super_admin(session, roles, report)
    await seed_hr_masters(session, report)

    companies = await seed_companies(session, report)
    case_types = await seed_case_types(session, report)
    await seed_import_template(session, report)
    await seed_form_templates(session, companies, case_types, report)
    await seed_document_templates(session, companies, case_types, report)

    return report
