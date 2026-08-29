"""Application settings, loaded from environment / .env."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Runtime configuration.

    Everything is overridable through environment variables so that no
    credential or environment-specific value ever lives in source control.
    """

    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------
    APP_NAME: str = "Investigation Management System"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    APP_TIMEZONE: str = "Asia/Kolkata"

    # --- Database ----------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/investigation_db"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # --- Security ----------------------------------------------------------
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 8

    # Login throttling
    LOGIN_MAX_ATTEMPTS: int = 8
    LOGIN_LOCKOUT_MINUTES: int = 15

    # --- Super admin bootstrap --------------------------------------------
    SUPER_ADMIN_NAME: str = "Super Administrator"
    SUPER_ADMIN_EMAIL: str = "admin@investigation.local"
    SUPER_ADMIN_PASSWORD: str = "Admin@123456"

    # --- Frontend / CORS ---------------------------------------------------
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Storage -----------------------------------------------------------
    STORAGE_DIR: Path = PROJECT_ROOT / "storage"
    MAX_UPLOAD_MB: int = 25
    MAX_IMPORT_MB: int = 40

    # --- Business defaults (overridable per-tenant in the settings table) ---
    ORGANIZATION_NAME: str = "Virtual Investigation Services"
    ORGANIZATION_SHORT_NAME: str = "VIPL"
    STAFF_ONLINE_TIMEOUT_MINUTES: int = 5
    DEFAULT_TAT_DAYS: int = 7
    TAT_BREACH_WARNING_HOURS: int = 24
    DATA_RETENTION_DAYS: int = 90
    CASE_NUMBER_PREFIX_INVESTIGATION: str = "INV"
    CASE_NUMBER_PREFIX_DEATH_CLAIM: str = "DCL"

    @field_validator("STORAGE_DIR", mode="before")
    @classmethod
    def _coerce_storage_dir(cls, value: object) -> Path:
        if isinstance(value, Path):
            return value
        if isinstance(value, str) and value.strip():
            return Path(value)
        return PROJECT_ROOT / "storage"

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def max_import_bytes(self) -> int:
        return self.MAX_IMPORT_MB * 1024 * 1024

    # Storage sub-directories -------------------------------------------------
    @property
    def case_documents_dir(self) -> Path:
        return self.STORAGE_DIR / "case_documents"

    @property
    def generated_documents_dir(self) -> Path:
        return self.STORAGE_DIR / "generated_documents"

    @property
    def template_originals_dir(self) -> Path:
        return self.STORAGE_DIR / "document_templates" / "original"

    @property
    def template_tagged_dir(self) -> Path:
        return self.STORAGE_DIR / "document_templates" / "tagged"

    @property
    def import_files_dir(self) -> Path:
        return self.STORAGE_DIR / "imports"

    def ensure_storage_dirs(self) -> None:
        for path in (
            self.case_documents_dir,
            self.generated_documents_dir,
            self.template_originals_dir,
            self.template_tagged_dir,
            self.import_files_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
