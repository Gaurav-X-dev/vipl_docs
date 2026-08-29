"""Dynamic form template and case-form payloads."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CaseCategory, CaseFormStatus, FieldSource, FieldType
from app.schemas.common import ORMModel


class FormFieldOut(ORMModel):
    id: uuid.UUID
    field_key: str
    label: str
    field_type: FieldType
    is_required: bool
    display_order: int
    col_span: int
    options: list[Any] | None = None
    default_value: str | None = None
    placeholder: str | None = None
    help_text: str | None = None
    validation_rules: dict[str, Any] | None = None
    table_columns: list[Any] | None = None
    source: FieldSource
    prefill_from: str | None = None
    document_mapping: str | None = None
    is_readonly: bool = False
    visible_when: str | None = None


class FormSectionOut(ORMModel):
    id: uuid.UUID
    key: str
    title: str
    description: str | None = None
    display_order: int
    is_repeatable: bool
    visible_when: str | None = None
    fields: list[FormFieldOut] = []


class FormTemplateOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    company_id: uuid.UUID
    company_name: str | None = None
    case_type_id: uuid.UUID
    case_type_name: str | None = None
    case_category: CaseCategory | None = None
    version: int
    is_active: bool
    description: str | None = None
    source_document: str | None = None
    section_count: int = 0
    field_count: int = 0
    created_at: datetime | None = None


class FormTemplateDetailOut(FormTemplateOut):
    sections: list[FormSectionOut] = []


class FieldValueOut(BaseModel):
    field_key: str
    value: str | None = None
    value_json: Any | None = None
    source: FieldSource = FieldSource.INVESTIGATION
    original_value: str | None = None
    original_column: str | None = None
    imported_at: datetime | None = None
    was_edited: bool = False
    updated_at: datetime | None = None


class CaseFormOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    template: FormTemplateDetailOut
    status: CaseFormStatus
    completion_percent: int
    submitted_at: datetime | None = None
    correction_remark: str | None = None
    values: dict[str, FieldValueOut] = Field(default_factory=dict)
    can_edit: bool = True
    #: Shown in place of the save bar when the form cannot be edited, so the
    #: reason is visible before anyone fills it in rather than after.
    locked_reason: str | None = None


class SaveFormRequest(BaseModel):
    """Partial save. Only the keys present are written."""

    values: dict[str, Any] = Field(default_factory=dict)
    submit: bool = False


class MissingFieldOut(BaseModel):
    """A required answer that is still empty, and where to find it."""

    field_key: str
    label: str
    section: str


class SaveFormResponse(BaseModel):
    status: CaseFormStatus
    completion_percent: int
    saved_fields: int
    missing_required: list[MissingFieldOut] = []
    message: str


# --------------------------------------------------------------------------- #
# Template administration
# --------------------------------------------------------------------------- #
class FormFieldIn(BaseModel):
    field_key: str = Field(min_length=1, max_length=96)
    label: str = Field(min_length=1, max_length=500)
    field_type: FieldType = FieldType.TEXT
    is_required: bool = False
    display_order: int = 0
    col_span: int = Field(default=6, ge=1, le=12)
    options: list[Any] | None = None
    default_value: str | None = None
    placeholder: str | None = None
    help_text: str | None = None
    validation_rules: dict[str, Any] | None = None
    table_columns: list[Any] | None = None
    source: FieldSource = FieldSource.INVESTIGATION
    prefill_from: str | None = None
    document_mapping: str | None = None
    is_readonly: bool = False
    visible_when: str | None = None


class FormSectionIn(BaseModel):
    key: str = Field(min_length=1, max_length=96)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    display_order: int = 0
    is_repeatable: bool = False
    visible_when: str | None = None
    fields: list[FormFieldIn] = Field(default_factory=list)


class FormTemplateIn(BaseModel):
    code: str = Field(min_length=1, max_length=96)
    name: str = Field(min_length=1, max_length=200)
    company_id: uuid.UUID
    case_type_id: uuid.UUID
    description: str | None = None
    is_active: bool = True
    sections: list[FormSectionIn] = Field(default_factory=list)
