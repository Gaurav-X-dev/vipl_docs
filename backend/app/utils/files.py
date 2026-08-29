"""Safe file storage helpers.

Rules enforced here:

* the browser-supplied filename is never used on disk;
* extension **and** magic bytes must both agree with an allow-list;
* every stored file gets a SHA-256 checksum;
* resolved paths must stay inside the configured storage root.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.core.errors import ValidationError
from app.utils.text import safe_filename

#: extension -> (allowed content types, magic prefixes)
ALLOWED_EVIDENCE_TYPES: dict[str, tuple[tuple[str, ...], tuple[bytes, ...]]] = {
    ".pdf": (("application/pdf",), (b"%PDF",)),
    ".jpg": (("image/jpeg",), (b"\xff\xd8\xff",)),
    ".jpeg": (("image/jpeg",), (b"\xff\xd8\xff",)),
    ".png": (("image/png",), (b"\x89PNG\r\n\x1a\n",)),
    ".webp": (("image/webp",), (b"RIFF",)),
    ".docx": (
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
        ),
        (b"PK\x03\x04",),
    ),
    ".xlsx": (
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream",
        ),
        (b"PK\x03\x04",),
    ),
}

ALLOWED_IMPORT_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".csv"}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_evidence_upload(filename: str, content_type: str, payload: bytes) -> tuple[str, str]:
    """Validate an evidence upload. Returns ``(extension, content_type)``."""
    if not payload:
        raise ValidationError("The uploaded file is empty.")
    if len(payload) > settings.max_upload_bytes:
        raise ValidationError(f"File is larger than the {settings.MAX_UPLOAD_MB} MB limit.")

    extension = Path(safe_filename(filename)).suffix.lower()
    if extension not in ALLOWED_EVIDENCE_TYPES:
        allowed = ", ".join(sorted(ALLOWED_EVIDENCE_TYPES))
        raise ValidationError(
            f"File type {extension or '(none)'} is not allowed. Allowed: {allowed}"
        )

    allowed_types, magic_prefixes = ALLOWED_EVIDENCE_TYPES[extension]
    if not any(payload.startswith(prefix) for prefix in magic_prefixes):
        raise ValidationError("The file content does not match its extension and was rejected.")
    normalised_type = (content_type or "").split(";")[0].strip().lower()
    if normalised_type and normalised_type not in allowed_types:
        # Trust the magic bytes, but record the declared type we accepted.
        normalised_type = allowed_types[0]
    return extension, normalised_type or allowed_types[0]


def validate_import_upload(filename: str, payload: bytes) -> str:
    if not payload:
        raise ValidationError("The uploaded file is empty.")
    if len(payload) > settings.max_import_bytes:
        raise ValidationError(f"Import file is larger than the {settings.MAX_IMPORT_MB} MB limit.")
    extension = Path(safe_filename(filename)).suffix.lower()
    if extension not in ALLOWED_IMPORT_EXTENSIONS:
        raise ValidationError("Only .xlsx, .xlsm, .xls and .csv files can be imported.")
    return extension


def build_stored_name(extension: str, prefix: str = "") -> str:
    """Generate a collision-free storage name. Never derived from user input."""
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    token = uuid.uuid4().hex[:12]
    head = f"{prefix}_" if prefix else ""
    return f"{head}{stamp}_{token}{extension}"


def dated_subdir(root: Path) -> Path:
    """``root/YYYY/MM`` — keeps directory listings manageable over years."""
    now = datetime.now(UTC)
    path = root / f"{now:%Y}" / f"{now:%m}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_bytes(target_dir: Path, stored_name: str, payload: bytes) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / stored_name
    path.write_bytes(payload)
    return path


def relative_to_storage(path: Path) -> str:
    """Store paths relative to the storage root so the tree stays movable."""
    try:
        return str(path.resolve().relative_to(settings.STORAGE_DIR.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def resolve_storage_path(relative_path: str) -> Path:
    """Resolve a stored relative path, refusing anything outside the root."""
    root = settings.STORAGE_DIR.resolve()
    candidate = (root / relative_path).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValidationError("Invalid file path.")
    return candidate
