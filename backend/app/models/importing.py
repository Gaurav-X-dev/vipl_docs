"""Excel / CSV import: templates, column mappings, batches and rows."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.company import Company
from app.models.enums import ImportBatchStatus, ImportRowStatus
from app.models.form import JSONVariant

if TYPE_CHECKING:
    from app.models.user import User


class ImportTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named Excel/CSV layout.

    ``VIPL_STANDARD_V1`` is seeded from the header strip in Image 3. Additional
    per-client layouts can be added without touching code.
    """

    __tablename__ = "import_templates"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: NULL means the template applies to files from any company.
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    header_row: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sheet_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Ordered list of internal field names forming the duplicate key.
    duplicate_key_fields: Mapped[list[str] | None] = mapped_column(JSONVariant, nullable=True)
    #: Secondary duplicate key used when the primary key columns are blank.
    fallback_duplicate_key_fields: Mapped[list[str] | None] = mapped_column(
        JSONVariant, nullable=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    company: Mapped[Company | None] = relationship(lazy="joined")
    mappings: Mapped[list[ImportColumnMapping]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ImportColumnMapping.display_order",
    )


class ImportColumnMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """External Excel header -> internal field name.

    Keeping this in the database is what lets the client change their Excel
    without a code release.
    """

    __tablename__ = "import_column_mappings"
    __table_args__ = (
        UniqueConstraint("template_id", "target_field", name="uq_import_mappings_template_field"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("import_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_column: Mapped[str] = mapped_column(String(160), nullable=False)
    #: Alternate spellings, pipe separated, matched case/space-insensitively.
    source_aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_field: Mapped[str] = mapped_column(String(64), nullable=False)
    data_type: Mapped[str] = mapped_column(String(24), nullable=False, default="text")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transform: Mapped[str | None] = mapped_column(String(48), nullable=True)
    validation_rules: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped[ImportTemplate] = relationship(back_populates="mappings", lazy="noload")

    @property
    def alias_list(self) -> list[str]:
        aliases = [self.source_column]
        if self.source_aliases:
            aliases += [a.strip() for a in self.source_aliases.split("|") if a.strip()]
        return aliases


class ImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One uploaded file and everything that happened to it."""

    __tablename__ = "import_batches"
    __table_args__ = (
        Index("ix_import_batches_status_created", "status", "created_at"),
        Index("ix_import_batches_checksum", "checksum_sha256"),
    )

    batch_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("import_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[ImportBatchStatus] = mapped_column(
        Enum(ImportBatchStatus, native_enum=False, length=32),
        nullable=False,
        default=ImportBatchStatus.UPLOADED,
    )
    detected_headers: Mapped[list[str] | None] = mapped_column(JSONVariant, nullable=True)
    #: Header -> internal field decided for this run (defaults + user overrides).
    applied_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped[ImportTemplate | None] = relationship(lazy="joined")
    company: Mapped[Company | None] = relationship(lazy="joined")
    uploaded_by: Mapped[User | None] = relationship(foreign_keys=[uploaded_by_id], lazy="joined")
    rows: Mapped[list[ImportRow]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="ImportRow.row_number",
    )


class ImportRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One spreadsheet row: raw snapshot, parsed values, and its verdict."""

    __tablename__ = "import_rows"
    __table_args__ = (
        Index("ix_import_rows_batch_status", "batch_id", "status"),
        UniqueConstraint("batch_id", "row_number", name="uq_import_rows_batch_row"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Verbatim snapshot of the source row — the auditable original.
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONVariant, nullable=False)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    status: Mapped[ImportRowStatus] = mapped_column(
        Enum(ImportRowStatus, native_enum=False, length=24),
        nullable=False,
        default=ImportRowStatus.PENDING,
    )
    errors: Mapped[list[str] | None] = mapped_column(JSONVariant, nullable=True)
    warnings: Mapped[list[str] | None] = mapped_column(JSONVariant, nullable=True)
    duplicate_of_case_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    created_case_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )

    batch: Mapped[ImportBatch] = relationship(back_populates="rows", lazy="noload")
