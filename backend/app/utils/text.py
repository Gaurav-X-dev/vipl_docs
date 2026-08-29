"""Small text helpers used by matching, imports and file handling."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_UNSAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def clean(value: object) -> str:
    """Trim and collapse internal whitespace; ``None`` becomes an empty string."""
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", str(value)).strip()


def normalise_key(value: object) -> str:
    """Lower-case, punctuation-free form used for fuzzy header/name matching.

    ``"Life_Assured_Name"``, ``"Life Assured Name"`` and ``"life-assured name"``
    all normalise to ``"lifeassuredname"``.
    """
    text = unicodedata.normalize("NFKD", clean(value)).lower()
    return _NON_ALNUM_RE.sub("", text)


def slugify(value: object, separator: str = "-") -> str:
    text = unicodedata.normalize("NFKD", clean(value)).lower()
    slug = _NON_ALNUM_RE.sub(separator, text).strip(separator)
    return slug or "item"


def safe_filename(value: str, fallback: str = "file") -> str:
    """Sanitise a browser-supplied filename. Never used as the storage name."""
    name = clean(value).replace("/", "_").replace("\\", "_")
    name = _UNSAFE_FILENAME_RE.sub("_", name).strip("._")
    if not name:
        name = fallback
    return name[:180]


def truncate(value: str | None, limit: int, suffix: str = "…") -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(0, limit - len(suffix))] + suffix


def mask_secret(value: str | None, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


def title_case(value: object) -> str:
    text = clean(value)
    return " ".join(word.capitalize() if word.islower() else word for word in text.split())


def yes_no(value: object) -> str:
    """Normalise the many yes/no spellings found across the client forms."""
    text = clean(value).lower()
    if text in {"y", "yes", "true", "1", "confirmed", "positive"}:
        return "YES"
    if text in {"n", "no", "false", "0", "not confirmed", "negative"}:
        return "NO"
    if text in {"", "na", "n/a", "not applicable", "-"}:
        return "NA"
    return clean(value).upper()
