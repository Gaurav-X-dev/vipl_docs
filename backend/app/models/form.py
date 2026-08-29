"""Dynamic, company-specific form templates and the values captured against them.

Each insurer supplied its own report layout (see ``docs/ATTACHMENT_ANALYSIS.md``
§6). Rather than hard-coding one giant React component per insurer, the layout is
data: ``FormTemplate -> FormSection -> FormField``, and the answers live in
``CaseFieldValue`` with full provenance and change history.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.company import CaseType, Company
from app.models.enums import CaseFormStatus, FieldSource, FieldType

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User

#: JSONB on PostgreSQL, plain JSON on SQLite (used by the test-suite).
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class FormTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A versioned form layout bound to one company and case type."""

    __tablename__ = "form_templates"
    __table_args__ = (
        UniqueConstraint("company_id", "case_type_id", "version", name="uq_form_templates_ccv"),
        Index("ix_form_templates_lookup", "company_id", "case_type_id", "is_active"),
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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The client .docx this layout was transcribed from.
    source_document: Mapped[str | None] = mapped_column(String(255), nullable=True)

    company: Mapped[Company] = relationship(lazy="joined")
    case_type: Mapped[CaseType] = relationship(lazy="joined")
    sections: Mapped[list[FormSection]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="FormSection.display_order",
    )


class FormSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "form_sections"
    __table_args__ = (UniqueConstraint("template_id", "key", name="uq_form_sections_template_key"),)

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("form_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(96), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Only shown when this expression evaluates true, e.g. "la_met == 'YES'".
    visible_when: Mapped[str | None] = mapped_column(String(255), nullable=True)

    template: Mapped[FormTemplate] = relationship(back_populates="sections", lazy="noload")
    fields: Mapped[list[FormField]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="FormField.display_order",
    )


class FormField(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "form_fields"
    __table_args__ = (
        UniqueConstraint("section_id", "field_key", name="uq_form_fields_section_key"),
        Index("ix_form_fields_section_order", "section_id", "display_order"),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("form_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(96), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    field_type: Mapped[FieldType] = mapped_column(
        Enum(FieldType, native_enum=False, length=24),
        nullable=False,
        default=FieldType.TEXT,
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Grid width out of 12 — lets the seeded layouts mirror the Word tables.
    col_span: Mapped[int] = mapped_column(Integer, nullable=False, default=6)

    options: Mapped[list[Any] | None] = mapped_column(JSONVariant, nullable=True)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    placeholder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rules: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    #: Column definitions when ``field_type`` is TABLE.
    table_columns: Mapped[list[Any] | None] = mapped_column(JSONVariant, nullable=True)

    source: Mapped[FieldSource] = mapped_column(
        Enum(FieldSource, native_enum=False, length=24),
        nullable=False,
        default=FieldSource.INVESTIGATION,
    )
    #: Case column (or import field) that pre-populates this field.
    prefill_from: Mapped[str | None] = mapped_column(String(96), nullable=True)
    #: Placeholder name used when rendering the client's .docx.
    document_mapping: Mapped[str | None] = mapped_column(String(96), nullable=True)
    is_readonly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visible_when: Mapped[str | None] = mapped_column(String(255), nullable=True)

    section: Mapped[FormSection] = relationship(back_populates="fields", lazy="noload")


class CaseForm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The instance of a template attached to one case."""

    __tablename__ = "case_forms"
    __table_args__ = (
        UniqueConstraint("case_id", "template_id", name="uq_case_forms_case_template"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("form_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    #: Frozen at attach time so a later template revision cannot rewrite history.
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[CaseFormStatus] = mapped_column(
        Enum(CaseFormStatus, native_enum=False, length=32),
        nullable=False,
        default=CaseFormStatus.DRAFT,
    )
    completion_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    correction_remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[Case] = relationship(back_populates="forms", lazy="noload")
    template: Mapped[FormTemplate] = relationship(lazy="selectin")
    values: Mapped[list[CaseFieldValue]] = relationship(
        back_populates="case_form", cascade="all, delete-orphan", lazy="selectin"
    )


class CaseFieldValue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One answer, with the provenance the client asked us never to lose."""

    __tablename__ = "case_field_values"
    __table_args__ = (
        UniqueConstraint("case_form_id", "field_key", name="uq_case_field_values_form_key"),
        Index("ix_case_field_values_form", "case_form_id"),
    )

    case_form_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("case_forms.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("form_fields.id", ondelete="SET NULL"), nullable=True
    )
    field_key: Mapped[str] = mapped_column(String(96), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Structured payload for TABLE / MULTI_SELECT fields.
    value_json: Mapped[Any | None] = mapped_column(JSONVariant, nullable=True)

    source: Mapped[FieldSource] = mapped_column(
        Enum(FieldSource, native_enum=False, length=24),
        nullable=False,
        default=FieldSource.INVESTIGATION,
    )
    #: Bank-supplied values are locked on import. Only the Super Admin can
    #: unlock one, and doing so writes an audit entry with a stated reason.
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unlocked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unlock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Original bank-supplied value, retained even after an investigator edits it.
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )
    original_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    case_form: Mapped[CaseForm] = relationship(back_populates="values", lazy="noload")


class CaseFieldValueHistory(UUIDPrimaryKeyMixin, Base):
    """Append-only trail of every change to a field value."""

    __tablename__ = "case_field_value_history"
    __table_args__ = (
        Index("ix_case_field_value_history_value", "case_field_value_id", "changed_at"),
    )

    case_field_value_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("case_field_values.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(96), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: Required when the edited field was locked bank-supplied data.
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    was_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    changed_by: Mapped[User | None] = relationship(lazy="joined")
