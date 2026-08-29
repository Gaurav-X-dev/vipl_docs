"""Writes the audit log and the human-readable case timeline.

Two views over the same events:

* :func:`record` writes a field-level ``audit_logs`` row for compliance;
* :func:`timeline` writes a plain-language ``case_timeline_events`` row for the
  case detail page.

Secrets never reach either table — :data:`REDACTED_KEYS` is stripped from every
diff before it is written.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog, CaseTimelineEvent
from app.models.enums import AuditAction
from app.models.user import User
from app.utils.dates import utcnow

REDACTED_KEYS = {
    "password",
    "raw_password",
    "new_password",
    "current_password",
    "password_hash",
    "refresh_token",
    "refresh_token_hash",
    "access_token",
    "token",
    "secret",
    "secret_key",
    "api_key",
}


def scrub(values: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop secrets and make the payload JSON-serialisable."""
    if not values:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in values.items():
        if key.lower() in REDACTED_KEYS:
            continue
        cleaned[key] = _jsonify(value)
    return cleaned or None


def _jsonify(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonify(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def diff(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict, dict]:
    """Return only the keys that actually changed."""
    old_values: dict[str, Any] = {}
    new_values: dict[str, Any] = {}
    for key, new in after.items():
        old = before.get(key)
        if _jsonify(old) != _jsonify(new):
            old_values[key] = old
            new_values[key] = new
    return old_values, new_values


def request_context(request: Request | None) -> dict[str, Any]:
    if request is None:
        return {}
    client_host = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_host = forwarded.split(",")[0].strip()
    return {
        "ip_address": client_host,
        "user_agent": request.headers.get("user-agent", "")[:500] or None,
        "request_method": request.method,
        "request_path": str(request.url.path)[:255],
        "request_id": getattr(request.state, "request_id", None),
    }


async def record(
    session: AsyncSession,
    *,
    action: AuditAction,
    module: str,
    actor: User | None = None,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    entity_label: str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    remarks: str | None = None,
    request: Request | None = None,
    actor_label: str | None = None,
) -> AuditLog:
    """Append one audit row. The caller owns the transaction."""
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_label=actor_label or (actor.full_name if actor else "System"),
        action=action,
        module=module,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        entity_label=entity_label,
        old_values=scrub(old_values),
        new_values=scrub(new_values),
        remarks=remarks,
        created_at=utcnow(),
        **request_context(request),
    )
    session.add(entry)
    return entry


async def timeline(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    event_type: str,
    summary: str,
    detail: str | None = None,
    actor: User | None = None,
    icon: str | None = None,
) -> CaseTimelineEvent:
    """Append one human-readable timeline entry for a case."""
    event = CaseTimelineEvent(
        case_id=case_id,
        actor_id=actor.id if actor else None,
        actor_label=actor.full_name if actor else "System",
        event_type=event_type,
        summary=summary[:500],
        detail=detail,
        icon=icon,
        occurred_at=utcnow(),
    )
    session.add(event)
    return event
