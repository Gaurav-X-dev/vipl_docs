"""Runtime application settings, backed by the ``app_settings`` table.

Environment variables seed the defaults on first boot; after that an
administrator edits them from the Settings screen without a redeploy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as env_settings
from app.models.misc import AppSetting


@dataclass(frozen=True)
class SettingDef:
    key: str
    label: str
    group: str
    value_type: str
    default: Any
    description: str = ""
    is_editable: bool = True


SETTING_DEFS: tuple[SettingDef, ...] = (
    SettingDef(
        "organization_name",
        "Organisation name",
        "Organisation",
        "string",
        env_settings.ORGANIZATION_NAME,
        "Printed on generated client reports.",
    ),
    SettingDef(
        "organization_short_name",
        "Short name",
        "Organisation",
        "string",
        env_settings.ORGANIZATION_SHORT_NAME,
        "Shown in the sidebar and on exports.",
    ),
    SettingDef("organization_address", "Address", "Organisation", "string", ""),
    SettingDef("organization_phone", "Phone", "Organisation", "string", ""),
    SettingDef("organization_email", "Email", "Organisation", "string", ""),
    SettingDef("organization_logo_path", "Logo path", "Organisation", "string", ""),
    SettingDef(
        "app_timezone",
        "Timezone",
        "Regional",
        "string",
        env_settings.APP_TIMEZONE,
        "IANA timezone used for every displayed timestamp.",
    ),
    SettingDef(
        "date_format",
        "Date format",
        "Regional",
        "string",
        "dd-MM-yyyy",
        "Display format for dates across the application.",
    ),
    SettingDef(
        "staff_online_timeout_minutes",
        "Staff online timeout (minutes)",
        "Staff",
        "int",
        env_settings.STAFF_ONLINE_TIMEOUT_MINUTES,
        "A staff member shows Online while their last activity is within this window.",
    ),
    SettingDef(
        "default_tat_days",
        "Default TAT (days)",
        "Cases",
        "int",
        env_settings.DEFAULT_TAT_DAYS,
        "Used when the company and case type do not define their own TAT.",
    ),
    SettingDef(
        "tat_breach_warning_hours",
        "TAT breach warning (hours)",
        "Cases",
        "int",
        env_settings.TAT_BREACH_WARNING_HOURS,
        "Cases due within this window are counted as 'about to breach'.",
    ),
    SettingDef(
        "case_prefix_investigation",
        "Investigation case prefix",
        "Cases",
        "string",
        env_settings.CASE_NUMBER_PREFIX_INVESTIGATION,
    ),
    SettingDef(
        "case_prefix_death_claim",
        "Death claim case prefix",
        "Cases",
        "string",
        env_settings.CASE_NUMBER_PREFIX_DEATH_CLAIM,
    ),
    SettingDef(
        "data_retention_days",
        "Data retention (days)",
        "Data",
        "int",
        env_settings.DATA_RETENTION_DAYS,
        "Completed cases older than this are eligible for the purge job (Image 2: '90 days data remove').",
    ),
    SettingDef(
        "max_upload_mb",
        "Maximum upload size (MB)",
        "Data",
        "int",
        env_settings.MAX_UPLOAD_MB,
    ),
    SettingDef(
        "agency_name",
        "Investigation agency name",
        "Reporting",
        "string",
        env_settings.ORGANIZATION_NAME,
        "Printed in the 'Investigation Agency Name' box of every client form.",
    ),
    SettingDef(
        "agency_contact",
        "Agency contact number",
        "Reporting",
        "string",
        "",
        "Printed in the agency contact box of client forms.",
    ),
    SettingDef(
        "agency_code",
        "Verification agency code",
        "Reporting",
        "string",
        "",
        "Some insurers print an agency code next to the agency name.",
    ),
)

_DEFS_BY_KEY = {definition.key: definition for definition in SETTING_DEFS}


def _serialise(value: Any, value_type: str) -> str:
    if value_type == "bool":
        return "true" if value else "false"
    if value_type == "json":
        import json

        return json.dumps(value)
    return "" if value is None else str(value)


async def ensure_defaults(session: AsyncSession) -> int:
    """Insert any settings that do not exist yet. Returns how many were added."""
    result = await session.execute(select(AppSetting.key))
    existing = set(result.scalars().all())
    created = 0
    for definition in SETTING_DEFS:
        if definition.key in existing:
            continue
        session.add(
            AppSetting(
                key=definition.key,
                value=_serialise(definition.default, definition.value_type),
                value_type=definition.value_type,
                group=definition.group,
                label=definition.label,
                description=definition.description,
                is_editable=definition.is_editable,
            )
        )
        created += 1
    return created


async def get_all(session: AsyncSession) -> list[AppSetting]:
    result = await session.execute(select(AppSetting).order_by(AppSetting.group, AppSetting.label))
    return list(result.scalars().all())


async def as_dict(session: AsyncSession) -> dict[str, Any]:
    return {row.key: row.typed_value() for row in await get_all(session)}


async def get_value(session: AsyncSession, key: str, default: Any = None) -> Any:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        definition = _DEFS_BY_KEY.get(key)
        return definition.default if definition else default
    value = row.typed_value()
    return default if value is None else value


async def get_int(session: AsyncSession, key: str, default: int) -> int:
    value = await get_value(session, key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def set_value(session: AsyncSession, key: str, value: Any) -> AppSetting:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        definition = _DEFS_BY_KEY.get(key)
        row = AppSetting(
            key=key,
            value_type=definition.value_type if definition else "string",
            group=definition.group if definition else "General",
            label=definition.label if definition else key.replace("_", " ").title(),
            description=definition.description if definition else None,
        )
        session.add(row)
    row.value = _serialise(value, row.value_type)
    return row
