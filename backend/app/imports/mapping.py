"""Excel header -> internal field resolution, and per-row value coercion.

External header text is never coupled to a database column name. The mapping
lives in ``import_column_mappings``; this module applies it, tolerating the
spelling and spacing drift that real client files always have.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.importing import ImportTemplate
from app.utils.dates import is_blank_token, parse_date
from app.utils.text import clean, normalise_key

#: Internal field names the importer understands, in Image-3 order.
CANONICAL_FIELDS: tuple[str, ...] = (
    "company_code",
    "case_type_code",
    "received_month",
    "received_at",
    "aging_days",
    "krn_no",
    "policy_number",
    "application_number",
    "life_assured_name",
    "city",
    "state",
    "assigned_to",
    "status",
    "import_remark",
    "pin_code",
    "report_date",
    "completion_date",
    "report_prepared_by",
    # Useful extras accepted when the client sends a wider file.
    "address",
    "contact_number",
    "alternate_contact",
    "email_id",
    "product_name",
    "sum_assured",
    "premium_amount",
    "risk_commencement_date",
    "nominee_name",
    "nominee_relation",
    "external_reference",
    "date_of_death",
    "place_of_death",
    "cause_of_death",
    "claimant_name",
    "claimant_relation",
)

FIELD_LABELS: dict[str, str] = {
    "company_code": "Company",
    "case_type_code": "Case Type",
    "received_month": "Month",
    "received_at": "Received Date",
    "aging_days": "Aging",
    "krn_no": "KRN No",
    "policy_number": "Policy Number",
    "application_number": "Application Number",
    "life_assured_name": "Life Assured Name",
    "city": "City",
    "state": "State",
    "assigned_to": "Assign To",
    "status": "Status",
    "import_remark": "Remark / ADD IO ID",
    "pin_code": "Pin Code",
    "report_date": "Report Date",
    "completion_date": "Completion Date",
    "report_prepared_by": "Report Prepared By",
    "address": "Address",
    "contact_number": "Contact Number",
    "alternate_contact": "Alternate Contact",
    "email_id": "Email",
    "product_name": "Product",
    "sum_assured": "Sum Assured",
    "premium_amount": "Premium Amount",
    "risk_commencement_date": "Risk Commencement Date",
    "nominee_name": "Nominee Name",
    "nominee_relation": "Nominee Relation",
    "external_reference": "External Reference",
    "date_of_death": "Date of Death",
    "place_of_death": "Place of Death",
    "cause_of_death": "Cause of Death",
    "claimant_name": "Claimant Name",
    "claimant_relation": "Claimant Relation",
}


@dataclass(slots=True)
class ResolvedMapping:
    """header -> internal field, plus what could not be matched."""

    header_to_field: dict[str, str | None] = field(default_factory=dict)
    field_to_header: dict[str, str] = field(default_factory=dict)
    unmapped_headers: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)


def resolve_mapping(
    headers: list[str],
    template: ImportTemplate,
    overrides: dict[str, str | None] | None = None,
) -> ResolvedMapping:
    """Match spreadsheet headers to internal fields."""
    alias_index: dict[str, str] = {}
    required_fields: set[str] = set()
    for mapping in template.mappings:
        for alias in mapping.alias_list:
            alias_index[normalise_key(alias)] = mapping.target_field
        # A header that simply *is* the internal field name also matches.
        alias_index.setdefault(normalise_key(mapping.target_field), mapping.target_field)
        if mapping.is_required:
            required_fields.add(mapping.target_field)

    resolved = ResolvedMapping()
    overrides = overrides or {}

    for header in headers:
        if header in overrides:
            target = overrides[header]
            resolved.header_to_field[header] = target
            if target:
                resolved.field_to_header.setdefault(target, header)
            else:
                resolved.unmapped_headers.append(header)
            continue

        key = normalise_key(header)
        target = alias_index.get(key)
        if target is None:
            # Fall back to a prefix match: "Application Numb" -> application_number.
            for alias_key, alias_target in alias_index.items():
                if (
                    alias_key
                    and (alias_key.startswith(key) or key.startswith(alias_key))
                    and min(len(alias_key), len(key)) >= 4
                ):
                    target = alias_target
                    break
        resolved.header_to_field[header] = target
        if target:
            resolved.field_to_header.setdefault(target, header)
        else:
            resolved.unmapped_headers.append(header)

    mapped_fields = set(resolved.field_to_header)
    resolved.missing_required = sorted(
        FIELD_LABELS.get(f, f) for f in required_fields - mapped_fields
    )
    return resolved


def coerce(value: Any, data_type: str) -> Any:
    """Convert one cell to the declared type. Returns ``None`` for blanks."""
    if is_blank_token(value):
        return None

    if data_type == "date":
        return parse_date(value)

    if data_type == "int":
        try:
            return int(Decimal(str(value).replace(",", "").strip()))
        except (InvalidOperation, ValueError, ArithmeticError):
            return None

    if data_type == "decimal":
        text = str(value).replace(",", "").replace("/-", "").strip()
        # Client files often write amounts as "5000000 /-" or "02 Lacs".
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None

    return clean(value)


def extract_row(
    raw: dict[str, Any], mapping: ResolvedMapping, template: ImportTemplate
) -> dict[str, Any]:
    """Apply the mapping to one raw row, producing internal field values."""
    types = {m.target_field: m.data_type for m in template.mappings}
    parsed: dict[str, Any] = {}
    for header, target in mapping.header_to_field.items():
        if not target:
            continue
        parsed[target] = coerce(raw.get(header), types.get(target, "text"))
    return parsed


def duplicate_signature(parsed: dict[str, Any], fields: list[str] | None) -> tuple[str, ...] | None:
    """Build the tuple used to spot duplicates inside a single file."""
    if not fields:
        return None
    parts: list[str] = []
    for name in fields:
        value = parsed.get(name)
        if value in (None, ""):
            return None
        parts.append(str(value).strip().lower())
    return tuple(parts)
