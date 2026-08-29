"""Administration: users, roles, permissions, settings, audit, notifications."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.pagination import Page, PageParams, page_params, paginate
from app.models.audit import AuditLog
from app.models.enums import AuditAction
from app.models.misc import AppSetting
from app.models.rbac import Permission, Role
from app.models.user import User
from app.schemas.common import IdResponse, Message
from app.schemas.misc import (
    AuditLogOut,
    NotificationCount,
    NotificationOut,
    PermissionOut,
    RoleIn,
    RoleOut,
    RolePermissionUpdate,
    SettingOut,
    SettingUpdate,
)
from app.services import audit_service, notification_service, settings_service
from app.utils.dates import end_of_day, start_of_day

router = APIRouter(tags=["Administration"])

ViewAudit = Annotated[User, Depends(require_permissions("audit.view"))]
ManageRoles = Annotated[User, Depends(require_permissions("roles.manage"))]
ManageSettings = Annotated[User, Depends(require_permissions("settings.manage"))]
ManageUsers = Annotated[User, Depends(require_permissions("users.manage"))]
PageDep = Annotated[PageParams, Depends(page_params)]


# --------------------------------------------------------------------------- #
# Roles and permissions
# --------------------------------------------------------------------------- #
@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(session: DbSession, user: ManageRoles) -> list[PermissionOut]:
    rows = (
        (await session.execute(select(Permission).order_by(Permission.module, Permission.code)))
        .scalars()
        .all()
    )
    return [PermissionOut.model_validate(row) for row in rows]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(session: DbSession, user: ManageRoles) -> list[RoleOut]:
    rows = (
        (
            await session.execute(
                select(Role)
                .options(selectinload(Role.permissions))
                .order_by(Role.is_system.desc(), Role.name)
            )
        )
        .unique()
        .scalars()
        .all()
    )

    from app.models.rbac import user_roles as user_roles_table

    counts = dict(
        (
            await session.execute(
                select(user_roles_table.c.role_id, func.count()).group_by(
                    user_roles_table.c.role_id
                )
            )
        ).all()
    )
    return [
        RoleOut(
            id=row.id,
            code=row.code,
            name=row.name,
            description=row.description,
            is_system=row.is_system,
            is_active=row.is_active,
            user_count=int(counts.get(row.id, 0)),
            permissions=sorted(row.permission_codes),
        )
        for row in rows
    ]


@router.post("/roles", response_model=IdResponse, status_code=201)
async def create_role(
    payload: RoleIn, request: Request, session: DbSession, user: ManageRoles
) -> IdResponse:
    existing = (
        await session.execute(select(Role).where(func.lower(Role.code) == payload.code.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Role code {payload.code} already exists.")

    permissions = (
        (
            await session.execute(
                select(Permission).where(Permission.code.in_(payload.permission_codes))
            )
        )
        .scalars()
        .all()
    )

    role = Role(
        code=payload.code.upper(),
        name=payload.name,
        description=payload.description,
        is_system=False,
        is_active=payload.is_active,
        permissions=list(permissions),
    )
    session.add(role)
    await session.flush()
    await audit_service.record(
        session,
        action=AuditAction.ROLE_CHANGED,
        module="Administration",
        actor=user,
        entity_type="Role",
        entity_id=role.id,
        entity_label=role.name,
        new_values={"permissions": payload.permission_codes},
        request=request,
    )
    await session.commit()
    return IdResponse(id=role.id, message="Role created.")


@router.put("/roles/{role_id}/permissions", response_model=Message)
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionUpdate,
    request: Request,
    session: DbSession,
    user: ManageRoles,
) -> Message:
    result = await session.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )
    role = result.unique().scalar_one_or_none()
    if role is None:
        raise NotFoundError("Role not found.")
    if role.code == "SUPER_ADMIN":
        raise ConflictError("The Super Admin role always holds every permission.")

    before = sorted(role.permission_codes)
    permissions = (
        (
            await session.execute(
                select(Permission).where(Permission.code.in_(payload.permission_codes))
            )
        )
        .scalars()
        .all()
    )
    unknown = set(payload.permission_codes) - {p.code for p in permissions}
    if unknown:
        raise ValidationError("Unknown permission codes.", details=sorted(unknown))
    role.permissions = list(permissions)

    await audit_service.record(
        session,
        action=AuditAction.PERMISSION_CHANGED,
        module="Administration",
        actor=user,
        entity_type="Role",
        entity_id=role.id,
        entity_label=role.name,
        old_values={"permissions": before},
        new_values={"permissions": sorted(payload.permission_codes)},
        request=request,
    )
    await session.commit()
    return Message(message=f"Permissions updated for {role.name}.")


@router.patch("/roles/{role_id}", response_model=Message)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleIn,
    request: Request,
    session: DbSession,
    user: ManageRoles,
) -> Message:
    role = await session.get(Role, role_id)
    if role is None:
        raise NotFoundError("Role not found.")
    if role.is_system and role.code != payload.code.upper():
        raise ConflictError("A system role's code cannot be changed.")
    role.name = payload.name
    role.description = payload.description
    role.is_active = payload.is_active
    await audit_service.record(
        session,
        action=AuditAction.ROLE_CHANGED,
        module="Administration",
        actor=user,
        entity_type="Role",
        entity_id=role.id,
        entity_label=role.name,
        request=request,
    )
    await session.commit()
    return Message(message="Role updated.")


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
@router.get("/users", response_model=Page[dict])
async def list_users(
    session: DbSession,
    user: ManageUsers,
    params: PageDep,
    search: str | None = Query(None),
) -> Page[dict]:
    statement = select(User).options(selectinload(User.roles)).order_by(User.full_name)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where((User.full_name.ilike(term)) | (User.email.ilike(term)))
    rows, total = await paginate(session, statement, params)
    timeout = await settings_service.get_int(session, "staff_online_timeout_minutes", 5)
    items = [
        {
            "id": str(row.id),
            "email": row.email,
            "full_name": row.full_name,
            "staff_category": row.staff_category.value,
            "is_active": row.is_active,
            "login_enabled": row.login_enabled,
            "is_super_admin": row.is_super_admin,
            "is_online": row.is_online(timeout),
            "roles": [role.name for role in row.roles],
            "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
        }
        for row in rows
    ]
    return Page.build(items, total, params)


@router.put("/users/{user_id}/roles", response_model=Message)
async def set_user_roles(
    user_id: uuid.UUID,
    request: Request,
    session: DbSession,
    user: ManageUsers,
    role_ids: Annotated[list[uuid.UUID], Body(embed=True)],
) -> Message:
    result = await session.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    target = result.unique().scalar_one_or_none()
    if target is None:
        raise NotFoundError("User not found.")
    if target.is_super_admin:
        raise ConflictError("The Super Admin's roles cannot be changed.")

    before = sorted(role.code for role in target.roles)
    roles = (await session.execute(select(Role).where(Role.id.in_(role_ids)))).scalars().all()
    target.roles = list(roles)

    await audit_service.record(
        session,
        action=AuditAction.ROLE_CHANGED,
        module="Administration",
        actor=user,
        entity_type="User",
        entity_id=target.id,
        entity_label=target.email,
        old_values={"roles": before},
        new_values={"roles": sorted(role.code for role in roles)},
        request=request,
    )
    await session.commit()
    return Message(message="Roles updated.")


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
@router.get("/settings", response_model=list[SettingOut])
async def list_settings(session: DbSession, user: ManageSettings) -> list[SettingOut]:
    rows = await settings_service.get_all(session)
    return [SettingOut.model_validate(row) for row in rows]


@router.put("/settings", response_model=Message)
async def update_settings(
    payload: SettingUpdate, request: Request, session: DbSession, user: ManageSettings
) -> Message:
    changed: dict[str, object] = {}
    for key, value in payload.values.items():
        row = (
            await session.execute(select(AppSetting).where(AppSetting.key == key))
        ).scalar_one_or_none()
        if row is not None and not row.is_editable:
            raise ConflictError(f"The setting '{key}' cannot be edited.")
        await settings_service.set_value(session, key, value)
        changed[key] = value

    await audit_service.record(
        session,
        action=AuditAction.SETTINGS_CHANGED,
        module="Administration",
        actor=user,
        entity_type="AppSetting",
        new_values=changed,
        request=request,
    )
    await session.commit()
    return Message(message=f"{len(changed)} setting(s) updated.")


@router.get("/settings/public")
async def public_settings(session: DbSession, user: CurrentUser) -> dict:
    """The handful of settings the frontend needs to render correctly."""
    values = await settings_service.as_dict(session)
    return {
        "organization_name": values.get("organization_name"),
        "organization_short_name": values.get("organization_short_name"),
        "app_timezone": values.get("app_timezone"),
        "date_format": values.get("date_format"),
        "staff_online_timeout_minutes": values.get("staff_online_timeout_minutes"),
        "tat_breach_warning_hours": values.get("tat_breach_warning_hours"),
        "data_retention_days": values.get("data_retention_days"),
    }


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #
@router.get("/audit-logs", response_model=Page[AuditLogOut])
async def list_audit_logs(
    session: DbSession,
    user: ViewAudit,
    params: PageDep,
    actor_id: uuid.UUID | None = Query(None),
    action: AuditAction | None = Query(None),
    module: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    search: str | None = Query(None),
) -> Page[AuditLogOut]:
    statement = (
        select(AuditLog).options(selectinload(AuditLog.actor)).order_by(AuditLog.created_at.desc())
    )
    if actor_id:
        statement = statement.where(AuditLog.actor_id == actor_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    if module:
        statement = statement.where(AuditLog.module == module)
    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)
    if entity_id:
        statement = statement.where(AuditLog.entity_id == entity_id)
    if date_from:
        statement = statement.where(AuditLog.created_at >= start_of_day(date_from))
    if date_to:
        statement = statement.where(AuditLog.created_at <= end_of_day(date_to))
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            (AuditLog.entity_label.ilike(term))
            | (AuditLog.actor_label.ilike(term))
            | (AuditLog.remarks.ilike(term))
        )

    rows, total = await paginate(session, statement, params)
    return Page.build([AuditLogOut.model_validate(row) for row in rows], total, params)


@router.get("/audit-logs/modules", response_model=list[str])
async def audit_modules(session: DbSession, user: ViewAudit) -> list[str]:
    rows = (
        (await session.execute(select(AuditLog.module).distinct().order_by(AuditLog.module)))
        .scalars()
        .all()
    )
    return list(rows)


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])


@notifications_router.get("", response_model=list[NotificationOut])
async def list_notifications(
    session: DbSession,
    user: CurrentUser,
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
) -> list[NotificationOut]:
    rows = await notification_service.list_for_user(
        session, user.id, unread_only=unread_only, limit=limit
    )
    return [NotificationOut.model_validate(row) for row in rows]


@notifications_router.get("/count", response_model=NotificationCount)
async def notification_count(session: DbSession, user: CurrentUser) -> NotificationCount:
    unread, total = await notification_service.counts(session, user.id)
    return NotificationCount(unread=unread, total=total)


@notifications_router.post("/read", response_model=Message)
async def mark_read(
    session: DbSession,
    user: CurrentUser,
    notification_ids: Annotated[list[uuid.UUID] | None, Body(embed=True)] = None,
) -> Message:
    count = await notification_service.mark_read(session, user.id, notification_ids)
    await session.commit()
    return Message(message=f"{count} notification(s) marked as read.")
