"""Date / time parsing and formatting helpers.

The daily Excel arrives with Indian day-first dates in several separators, and
occasionally as an Excel serial number, so parsing is deliberately forgiving —
but never ambiguous: day-first always wins over month-first.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings

_EXCEL_EPOCH = date(1899, 12, 30)  # Excel's (buggy) serial-date origin

_DATE_PATTERNS: tuple[str, ...] = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%d-%m-%y",
    "%d/%m/%y",
    "%d.%m.%y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%B-%Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)

_DATETIME_PATTERNS: tuple[str, ...] = (
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %I:%M %p",
    "%d-%m-%Y %I:%M %p",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)

_NULL_TOKENS = {
    "",
    "-",
    "--",
    "na",
    "n/a",
    "nil",
    "none",
    "null",
    "not shared",
    "not disclosed",
    "not applicable",
    "not confirm",
}


def app_timezone() -> ZoneInfo | timezone:
    try:
        return ZoneInfo(settings.APP_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):  # pragma: no cover - misconfig guard
        # ``timezone.utc`` remains available on minimal Windows/Python images
        # even when the optional IANA timezone database is absent.
        return UTC


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_app_tz(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(app_timezone())


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_blank_token(raw: object) -> bool:
    """True for the many ways these forms spell "no value"."""
    if raw is None:
        return True
    text = str(raw).strip().lower()
    return text in _NULL_TOKENS


def parse_date(raw: object) -> date | None:
    """Best-effort day-first date parsing. Returns ``None`` when unparseable."""
    if raw is None or is_blank_token(raw):
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return _from_excel_serial(float(raw))

    text = str(raw).strip()
    if not text:
        return None

    # A bare number in a text cell is still an Excel serial.
    if re.fullmatch(r"\d{5}(\.\d+)?", text):
        return _from_excel_serial(float(text))

    for pattern in _DATETIME_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def parse_datetime(raw: object) -> datetime | None:
    if raw is None or is_blank_token(raw):
        return None
    if isinstance(raw, datetime):
        return ensure_utc(raw)
    text = str(raw).strip()
    for pattern in _DATETIME_PATTERNS:
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    parsed_date = parse_date(text)
    if parsed_date:
        return datetime.combine(parsed_date, time.min, tzinfo=UTC)
    return None


def _from_excel_serial(serial: float) -> date | None:
    if serial <= 0 or serial > 100_000:
        return None
    return _EXCEL_EPOCH + timedelta(days=int(serial))


def start_of_day(value: date) -> datetime:
    """Midnight of ``value`` in the application timezone, returned as UTC."""
    local = datetime.combine(value, time.min, tzinfo=app_timezone())
    return local.astimezone(UTC)


def end_of_day(value: date) -> datetime:
    local = datetime.combine(value, time.max, tzinfo=app_timezone())
    return local.astimezone(UTC)


def format_date(value: date | datetime | None, fmt: str = "%d-%m-%Y") -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        localised = to_app_tz(value)
        return localised.strftime(fmt) if localised else ""
    return value.strftime(fmt)


def format_datetime(value: datetime | None, fmt: str = "%d-%m-%Y %I:%M %p") -> str:
    localised = to_app_tz(value)
    return localised.strftime(fmt) if localised else ""


def days_between(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    start_utc = ensure_utc(start)
    end_utc = ensure_utc(end)
    if start_utc is None or end_utc is None:
        return None
    return (end_utc - start_utc).days
