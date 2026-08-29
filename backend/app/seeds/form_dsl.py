"""A small DSL for declaring seeded form layouts.

Keeps the twenty insurer forms readable: ``T`` is a template, ``S`` a section,
``F`` a field. Common option sets used across the client documents live here too,
spelled exactly as the forms spell them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import CaseCategory, FieldSource, FieldType

# --------------------------------------------------------------------------- #
# Option sets taken verbatim from the supplied forms
# --------------------------------------------------------------------------- #
YES_NO = ["Yes", "No"]
YES_NO_NA = ["Yes", "No", "NA"]
POSITIVE_NEGATIVE = ["Positive", "Negative", "Suspicious"]
INTERIM_FINAL = ["Interim", "Final"]
MET_NOT_MET = ["Met", "Not met", "Refused to meet", "Not traceable"]
MARITAL_STATUS = ["Married", "Unmarried", "Widowed", "Divorced", "Not disclosed"]
OCCUPATION_TYPE = [
    "Salaried",
    "Self-employed / Business",
    "Professional",
    "Farmer / Agriculture",
    "Housewife",
    "Student",
    "Retired",
    "Labour",
    "Unemployed",
    "Not disclosed",
]
STANDARD_OF_LIVING = [
    "High income group",
    "Upper middle class",
    "Middle class",
    "Lower middle class",
    "APL",
    "BPL",
    "Not assessed",
]
LOCALITY = ["Urban", "Semi-urban", "Rural", "Slum", "Gated community"]
HOUSE_TYPE = [
    "Single storey",
    "Double storey",
    "Multi storey",
    "Flat / Apartment",
    "Bungalow",
    "Hut / Kutcha",
]
OWNERSHIP = ["Owned house", "Rented", "Parental house", "Company provided", "Not confirmed"]
FEEDBACK = ["Positive", "Negative", "Mixed", "Not available"]
KEY_SENSING = ["Yes", "No", "Suspected", "Not applicable"]
EVIDENCE_STATUS = ["Attached", "Not shared", "Not applicable", "Awaited"]
HEALTH_STATUS = [
    "Fit and healthy",
    "Minor ailment",
    "Chronic illness",
    "Terminally ill",
    "Deceased",
    "Not assessed",
]

#: Repeating-table column sets, one per table found in the client documents.
FAMILY_COLUMNS = [
    {"key": "name", "label": "Name"},
    {"key": "relation", "label": "Relation with LA"},
    {"key": "age", "label": "Age"},
    {"key": "occupation", "label": "Occupation"},
    {"key": "income", "label": "Income"},
    {"key": "health", "label": "Health"},
    {"key": "kyc", "label": "KYC proof"},
]

NEIGHBOUR_COLUMNS = [
    {"key": "name", "label": "Name of the person"},
    {"key": "relation", "label": "Relation with insured"},
    {"key": "place", "label": "Place (residence / workplace)"},
    {"key": "contact", "label": "Contact no"},
    {"key": "address", "label": "Address"},
    {"key": "remarks", "label": "Statement / remarks"},
]

HOSPITAL_COLUMNS = [
    {"key": "name", "label": "Hospital / Lab / Chemist"},
    {"key": "person", "label": "Contact person"},
    {"key": "location", "label": "Location"},
    {"key": "contact", "label": "Contact no"},
    {"key": "visit_date", "label": "Date of visit"},
    {"key": "findings", "label": "Findings / evidence"},
]

OTHER_POLICY_COLUMNS = [
    {"key": "company", "label": "Name of company"},
    {"key": "insured", "label": "Life insured / proposer"},
    {"key": "contract_no", "label": "Contract / proposal no"},
    {"key": "sum_assured", "label": "Sum assured"},
    {"key": "rcd", "label": "RCD"},
    {"key": "status", "label": "Policy status"},
]

DOCUMENT_COLUMNS = [
    {"key": "particulars", "label": "Particulars"},
    {"key": "collected", "label": "Evidence collected"},
    {"key": "source", "label": "Source of procurement"},
    {"key": "verified_by", "label": "Verified by"},
    {"key": "dates", "label": "Date"},
]

PROPOSAL_MATCH_COLUMNS = [
    {"key": "detail", "label": "Detail"},
    {"key": "as_per_proposal", "label": "In proposal form"},
    {"key": "as_per_investigation", "label": "During investigation"},
    {"key": "discrepancy", "label": "Discrepancy noted"},
    {"key": "evidence", "label": "Evidence received"},
]


@dataclass(frozen=True)
class F:
    """One form field."""

    key: str
    label: str
    type: FieldType = FieldType.TEXT
    required: bool = False
    options: list | None = None
    prefill: str | None = None
    source: FieldSource = FieldSource.INVESTIGATION
    doc: str | None = None
    help: str | None = None
    col_span: int = 6
    readonly: bool = False
    columns: list | None = None
    default: str | None = None

    def as_kwargs(self, order: int) -> dict:
        return {
            "field_key": self.key,
            "label": self.label,
            "field_type": self.type,
            "is_required": self.required,
            "display_order": order,
            "col_span": self.col_span,
            "options": self.options,
            "default_value": self.default,
            "help_text": self.help,
            "table_columns": self.columns,
            "source": self.source,
            "prefill_from": self.prefill,
            "document_mapping": self.doc or self.key,
            "is_readonly": self.readonly,
        }


def BANK(
    key: str,
    label: str,
    prefill: str,
    *,
    type: FieldType = FieldType.TEXT,
    doc: str | None = None,
    col_span: int = 6,
) -> F:
    """A field the bank supplies — pre-filled, badged, and never re-keyed."""
    return F(
        key,
        label,
        type=type,
        prefill=prefill,
        source=FieldSource.BANK_SUPPLIED,
        doc=doc or prefill,
        col_span=col_span,
    )


def NARRATIVE(key: str, label: str, doc: str | None = None) -> F:
    return F(key, label, type=FieldType.TEXTAREA, doc=doc, col_span=12)


def TABLE(key: str, label: str, columns: list, doc: str | None = None) -> F:
    return F(key, label, type=FieldType.TABLE, columns=columns, doc=doc, col_span=12)


@dataclass(frozen=True)
class S:
    """One form section."""

    key: str
    title: str
    fields: list[F] = field(default_factory=list)
    description: str | None = None
    repeatable: bool = False


@dataclass(frozen=True)
class T:
    """One form template, bound to a company and case type."""

    code: str
    name: str
    company: str
    case_type: str
    source_document: str
    sections: list[S] = field(default_factory=list)
    description: str | None = None

    @property
    def category(self) -> CaseCategory:
        return (
            CaseCategory.DEATH_CLAIM
            if self.case_type in {"DEATH_CLAIM", "DEATH_CLAIM_FTI", "LANDLORD_VERIFICATION"}
            else CaseCategory.INVESTIGATION
        )


# --------------------------------------------------------------------------- #
# Reusable section builders — these blocks repeat across nearly every insurer
# --------------------------------------------------------------------------- #
def agency_section(prefix: str = "") -> S:
    return S(
        "investigator_details",
        "Investigator details",
        [
            F(
                "agency_name",
                "Investigation agency name",
                doc="agency_name",
                default="Virtual Investigation Services",
            ),
            F(
                "field_investigator_name",
                "Field investigator name",
                prefill="assigned_to_name",
                doc="field_investigator_name",
            ),
            F(
                "fi_contact_number",
                "Contact number of field investigator",
                type=FieldType.PHONE,
                doc="fi_contact_number",
            ),
            BANK(
                "assignment_date",
                "Investigation assignment date",
                "received_at",
                type=FieldType.DATE,
                doc="assignment_date",
            ),
            F("date_of_visit", "Date of visit", type=FieldType.DATE, doc="date_of_visit"),
            F("time_of_visit", "Time of visit", type=FieldType.TIME, doc="time_of_visit"),
            F(
                "report_submission_date",
                "Report submission date",
                type=FieldType.DATE,
                doc="report_submission_date",
            ),
            F(
                "tat_days",
                "Time taken (TAT)",
                doc="tat_days",
                help="Auto-calculated on generation if left blank.",
            ),
        ],
    )


def policy_section(extra: list[F] | None = None) -> S:
    fields = [
        BANK("policy_number", "Policy number", "policy_number"),
        BANK("application_number", "Application number", "application_number"),
        BANK("krn_no", "KRN / reference number", "krn_no"),
        BANK("life_assured_name", "Name of Life Assured", "life_assured_name"),
        BANK(
            "la_address",
            "Address as per policy",
            "address",
            type=FieldType.TEXTAREA,
            doc="la_address",
            col_span=12,
        ),
        BANK("contact_number", "Contact number", "contact_number", type=FieldType.PHONE),
        BANK("alternate_contact", "Alternate number", "alternate_contact", type=FieldType.PHONE),
        BANK("city", "City", "city"),
        BANK("state", "State", "state"),
        BANK("pin_code", "Pin code", "pin_code"),
    ]
    if extra:
        fields.extend(extra)
    return S("policy_details", "Policy / proposal details", fields)


def outcome_section(with_report_status: bool = True) -> S:
    fields = [
        F(
            "outcome",
            "Investigation outcome",
            type=FieldType.SELECT,
            options=POSITIVE_NEGATIVE,
            required=True,
            doc="outcome",
        ),
        NARRATIVE("conclusion", "Conclusion / recommendation", doc="conclusion"),
    ]
    if with_report_status:
        fields.insert(
            0,
            F(
                "report_status",
                "Report status",
                type=FieldType.SELECT,
                options=INTERIM_FINAL,
                required=True,
                doc="report_status",
            ),
        )
    return S("conclusion", "Conclusion", fields)


def photographs_section(labels: list[str]) -> S:
    return S(
        "photographs",
        "Photographs (geo-tagged)",
        [
            F(
                f"photo_{index}",
                label,
                type=FieldType.IMAGE,
                col_span=6,
                help="Upload under the Documents tab with location tagging.",
            )
            for index, label in enumerate(labels, start=1)
        ],
        description=("Photographs must carry location tagging with a date and time stamp."),
    )
