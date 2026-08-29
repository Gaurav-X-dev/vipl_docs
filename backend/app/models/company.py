"""Client master: companies (banks / insurers) and case types."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CaseCategory, CompanyType


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A bank, insurer or other client that sends cases."""

    __tablename__ = "companies"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False)
    company_type: Mapped[CompanyType] = mapped_column(
        Enum(CompanyType, native_enum=False, length=32),
        nullable=False,
        default=CompanyType.INSURANCE,
    )

    #: Extra spellings seen in the daily Excel, matched case-insensitively.
    import_aliases: Mapped[str | None] = mapped_column(Text, nullable=True)

    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pin_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    #: Default turn-around time in days for this client's cases.
    default_tat_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def alias_list(self) -> list[str]:
        if not self.import_aliases:
            return []
        return [a.strip() for a in self.import_aliases.split("|") if a.strip()]


class CaseType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A kind of assignment, e.g. Pre-Issuance, Discreet Check, Death Claim."""

    __tablename__ = "case_types"

    code: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[CaseCategory] = mapped_column(
        Enum(CaseCategory, native_enum=False, length=24), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_tat_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    @property
    def alias_list(self) -> list[str]:
        if not self.import_aliases:
            return []
        return [a.strip() for a in self.import_aliases.split("|") if a.strip()]
