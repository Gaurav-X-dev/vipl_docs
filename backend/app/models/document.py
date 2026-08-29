"""Client document templates (.docx) and the documents generated from them."""

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
from app.models.company import CaseType, Company
from app.models.enums import DocumentTemplateStatus, GeneratedFormat
from app.models.form import JSONVariant

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User


class DocumentTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A client's Word form, kept verbatim and rendered with ``docxtpl``.

    Two files are tracked per template:

    * ``original_path`` — the untouched file the client supplied. Never
      overwritten; a new revision creates a new row with ``version`` + 1.
    * ``tagged_path`` — the same document with specimen values replaced by
      ``{{ placeholder }}`` tags. This is what generation actually renders.
    """

    __tablename__ = "document_templates"
    __table_args__ = (
        UniqueConstraint("company_id", "case_type_id", "version", name="uq_document_templates_ccv"),
        Index("ix_document_templates_lookup", "company_id", "case_type_id", "status"),
    )

    code: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    case_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("case_types.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[DocumentTemplateStatus] = mapped_column(
        Enum(DocumentTemplateStatus, native_enum=False, length=32),
        nullable=False,
        default=DocumentTemplateStatus.ACTIVE,
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    tagged_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    #: Placeholder -> human description, produced by ``scripts/tag_templates.py``.
    placeholder_map: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    company: Mapped[Company] = relationship(lazy="joined")
    case_type: Mapped[CaseType] = relationship(lazy="joined")

    @property
    def can_generate_docx(self) -> bool:
        return self.status == DocumentTemplateStatus.ACTIVE and bool(self.tagged_path)


class GeneratedDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A rendered client form. Immutable once written."""

    __tablename__ = "generated_documents"
    __table_args__ = (Index("ix_generated_documents_case_created", "case_id", "created_at"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_format: Mapped[GeneratedFormat] = mapped_column(
        Enum(GeneratedFormat, native_enum=False, length=16), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: False when the DOCX template was unavailable and the PDF fallback ran.
    used_client_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    case: Mapped[Case] = relationship(lazy="noload")
    template: Mapped[DocumentTemplate | None] = relationship(lazy="joined")
    generated_by: Mapped[User | None] = relationship(lazy="joined")
