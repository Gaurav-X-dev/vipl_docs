"""Password hashing and JWT helpers."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(raw_password: str) -> str:
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, raw_password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False
    return True


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return True


_PASSWORD_RULES = (
    (re.compile(r"[a-z]"), "one lowercase letter"),
    (re.compile(r"[A-Z]"), "one uppercase letter"),
    (re.compile(r"[0-9]"), "one digit"),
)


def validate_password_strength(raw_password: str) -> list[str]:
    """Return a list of human-readable problems; empty list means acceptable."""
    problems: list[str] = []
    if len(raw_password) < settings.PASSWORD_MIN_LENGTH:
        problems.append(f"must be at least {settings.PASSWORD_MIN_LENGTH} characters long")
    for pattern, description in _PASSWORD_RULES:
        if not pattern.search(raw_password):
            problems.append(f"must contain at least {description}")
    return problems


def generate_temporary_password(length: int = 14) -> str:
    """Generate a password that always satisfies the strength rules."""
    alphabet = "abcdefghijkmnopqrstuvwxyz"
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    specials = "@#$%&*!?"
    pool = alphabet + upper + digits + specials
    core = [
        secrets.choice(alphabet),
        secrets.choice(upper),
        secrets.choice(digits),
        secrets.choice(specials),
    ]
    core += [secrets.choice(pool) for _ in range(max(0, length - len(core)))]
    secrets.SystemRandom().shuffle(core)
    return "".join(core)


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(UTC)


def create_token(
    subject: str,
    token_type: TokenType,
    session_id: str | None = None,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    """Build a signed JWT. Returns ``(token, expires_at)``."""
    if expires_delta is None:
        expires_delta = (
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            if token_type == "access"
            else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
    issued_at = _now()
    expires_at = issued_at + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if session_id:
        payload["sid"] = session_id
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode and validate a JWT. Raises ``jwt.PyJWTError`` on any problem."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"expected a {expected_type} token, got {payload.get('type')!r}"
        )
    return payload
