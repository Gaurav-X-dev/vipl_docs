"""Date / time parsing and formatting helpers.

The daily Excel arrives with Indian day-first dates in several separators, and
occasionally as an Excel serial number, so parsing is deliberately forgiving —
but never ambiguous: day-first always wins over month-first.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta, timezone
from collections.abc import Iterable
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

#: The same list with the day and month swapped, for sheets written in the
#: American order. Which of the two is used is decided per file, not per cell:
#: see ``detect_month_first``.
_MONTH_FIRST_DATE_PATTERNS: tuple[str, ...] = (
    "%m-%d-%Y",
    "%m/%d/%Y",
    "%m.%d.%Y",
    "%m-%d-%y",
    "%m/%d/%y",
    "%m.%d.%y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%B-%Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)

_MONTH_FIRST_DATETIME_PATTERNS: tuple[str, ...] = (
    "%m-%d-%Y %H:%M:%S",
    "%m-%d-%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M %p",
    "%m-%d-%Y %I:%M %p",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
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


_NUMERIC_DATE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$")


def detect_month_first(samples: Iterable[object]) -> bool:
    """Decide whether a column of dates is written month-first.

    Client sheets disagree: most Indian insurers send ``24-08-2026`` and at
    least one sends ``8/24/2026``. Guessing per cell is what makes this
    dangerous — ``8/6/2026`` is a valid date either way, and reading it wrongly
    silently shifts the aging and the TAT by two months.

    So the whole column decides. A component above twelve can only be a day,
    which settles the order for every other cell in the file. With no evidence,
    or with both orders apparently present, the day-first default stands.
    """
    day_first_evidence = False
    month_first_evidence = False

    for sample in samples:
        if not isinstance(sample, str):
            continue
        match = _NUMERIC_DATE.match(sample.strip())
        if not match:
            continue
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12 >= second:
            day_first_evidence = True
        elif second > 12 >= first:
            month_first_evidence = True

    return month_first_evidence and not day_first_evidence


def parse_date(raw: object, *, month_first: bool = False) -> date | None:
    """Best-effort date parsing. Returns ``None`` when unparseable.

    Day-first unless ``month_first`` is set, which the importer decides once
    per file from ``detect_month_first``.
    """
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

    datetime_patterns = (
        _MONTH_FIRST_DATETIME_PATTERNS if month_first else _DATETIME_PATTERNS
    )
    date_patterns = _MONTH_FIRST_DATE_PATTERNS if month_first else _DATE_PATTERNS
    for pattern in datetime_patterns:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    for pattern in date_patterns:
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
