"""Companies, case types and the standard import template.

Every entry is derived from a supplied attachment — see
``docs/ATTACHMENT_ANALYSIS.md`` §1 and §4. Aliases are the spellings actually
seen in the client's files, so the importer resolves them without manual mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import CaseCategory, CompanyType


@dataclass(frozen=True)
class CompanySeed:
    code: str
    name: str
    short_name: str
    company_type: CompanyType
    aliases: tuple[str, ...] = ()
    default_tat_days: int = 7


COMPANIES: tuple[CompanySeed, ...] = (
    CompanySeed(
        "ABSLI",
        "Aditya Birla Sun Life Insurance Company Limited",
        "Aditya Birla Life",
        CompanyType.INSURANCE,
        ("Aditya Birla", "ABSLI", "Birla Sun Life", "Aditya Birla Sun Life"),
    ),
    CompanySeed(
        "BAJAJ",
        "Bajaj Allianz Life Insurance Company Limited",
        "Bajaj Allianz Life",
        CompanyType.INSURANCE,
        ("Bajaj", "Bajaj Allianz", "Bajaj Life"),
    ),
    CompanySeed(
        "BAXA",
        "Bharti AXA Life Insurance Company Limited",
        "Bharti AXA Life",
        CompanyType.INSURANCE,
        ("BAXA", "BXA", "Bharti AXA", "Bharti Axa Life"),
    ),
    CompanySeed(
        "BANDHAN",
        "Bandhan Life Insurance Limited",
        "Bandhan Life",
        CompanyType.INSURANCE,
        ("Bandhan", "Bandhan Life Insurance", "Aegon", "Aegon Life"),
    ),
    CompanySeed(
        "HDFC",
        "HDFC Life Insurance Company Limited",
        "HDFC Life",
        CompanyType.INSURANCE,
        ("HDFC", "HDFC Life", "HDFC Standard Life"),
    ),
    CompanySeed(
        "HSBC",
        "Canara HSBC Life Insurance Company Limited",
        "Canara HSBC Life",
        CompanyType.INSURANCE,
        ("HSBC", "Canara HSBC", "Canara", "Canera", "HSBC Canara", "Canara HSBC OBC"),
    ),
    CompanySeed(
        "ICICI",
        "ICICI Prudential Life Insurance Company Limited",
        "ICICI Prudential",
        CompanyType.INSURANCE,
        ("ICICI", "ICICI Pru", "ICICI Prudential", "IPRU"),
    ),
    CompanySeed(
        "KOTAK",
        "Kotak Mahindra Life Insurance Company Limited",
        "Kotak Life",
        CompanyType.INSURANCE,
        ("Kotak", "Kotak Life", "Kotak Mahindra"),
    ),
    CompanySeed(
        "PNBMET",
        "PNB MetLife India Insurance Company Limited",
        "PNB MetLife",
        CompanyType.INSURANCE,
        ("PNB", "PNB MetLife", "MetLife", "PNB Met"),
    ),
    CompanySeed(
        "SUD",
        "Star Union Dai-ichi Life Insurance Company Limited",
        "SUD Life",
        CompanyType.INSURANCE,
        ("SUD", "SUD Life", "Star Union", "Star Union Dai-ichi"),
    ),
)


@dataclass(frozen=True)
class CaseTypeSeed:
    code: str
    name: str
    category: CaseCategory
    description: str
    aliases: tuple[str, ...] = ()
    default_tat_days: int = 7
    display_order: int = 100


CASE_TYPES: tuple[CaseTypeSeed, ...] = (
    CaseTypeSeed(
        "PRE_ISSUANCE",
        "Pre-Issuance Verification",
        CaseCategory.INVESTIGATION,
        "Verification of a proposal before the policy is issued.",
        (
            "Pre Issuance",
            "Pre-Issuance",
            "PIV",
            "Pre Issuance Verification",
            "New Business",
            "Fresh",
            # Aditya Birla's daily sheet splits the same verification into
            # three labels of its own. They are one form, so they route here
            # and the sheet's own wording stays visible on the Imported data
            # tab.
            "Project Verification",
            "Physical Verification",
            "Post Verification",
            # Bandhan and Canara HSBC both file these against their
            # pre-issuance form; scoped so "Post Issuance" does not become a
            # global synonym for its own opposite.
            "BANDHAN:Post Issuance",
            "HSBC:Post Issuance",
        ),
        display_order=10,
    ),
    CaseTypeSeed(
        "PRE_CLAIM",
        "Pre-Claim Verification",
        CaseCategory.INVESTIGATION,
        "Early-claim verification of the life assured's profile and existence.",
        (
            "Pre Claim",
            "Pre-Claim",
            "Preclaim",
            "Early Claim",
            # Each insurer's own word for the work its one form covers.
            "PNBMET:Retail",
            "KOTAK:PIPV",
        ),
        display_order=20,
    ),
    CaseTypeSeed(
        "PROFILE_CHECK",
        "Profile Check",
        CaseCategory.INVESTIGATION,
        "Detailed profile verification against the proposal form.",
        (
            "Profile Check",
            "Customer Profile Verification",
            "Profile Verification",
            "ADD",
            "Add Manual",
        ),
        display_order=30,
    ),
    CaseTypeSeed(
        "DISCREET_CHECK",
        "Discreet Check",
        CaseCategory.INVESTIGATION,
        "Vicinity-only enquiry conducted without approaching the life assured.",
        ("Discreet Check", "Discreate Check", "Discreet", "Vicinity Check"),
        default_tat_days=5,
        display_order=40,
    ),
    CaseTypeSeed(
        "PAYOUT_VERIFICATION",
        "Payout Verification",
        CaseCategory.INVESTIGATION,
        "Confirmation of the customer and address before a payout is released.",
        ("Payout", "Payout Verification", "Pay Out", "ICICI:Policy Assignment"),
        default_tat_days=5,
        display_order=50,
    ),
    CaseTypeSeed(
        "NEW_BUSINESS_VERIFICATION",
        "Customer Verification – New Business",
        CaseCategory.INVESTIGATION,
        "New-business customer verification captured in the client's LMS format.",
        (
            "LMS",
            "New Business Verification",
            "Customer Verification",
            "Manual Report",
            # ICICI's LMS document is their pre-issuance form. This used to be
            # hard-coded in the resolver; it belongs with the other wording.
            "ICICI:Pre Issuance",
            "ICICI:Pre-Issuance",
            "ICICI:PIV",
        ),
        display_order=60,
    ),
    CaseTypeSeed(
        "MEDICAL_SEEDING",
        "Medical Seeding / Mystery Shopping",
        CaseCategory.INVESTIGATION,
        "Integrity check of a diagnostic centre using a seeded candidate.",
        ("Medical Seeding", "Mystery Shopping", "Mistry Shopping", "Seeding"),
        default_tat_days=10,
        display_order=70,
    ),
    CaseTypeSeed(
        "DEATH_CLAIM",
        "Death Claim Investigation",
        CaseCategory.DEATH_CLAIM,
        "Full death / critical illness / hospital rider claim investigation.",
        (
            "Death Claim",
            "Death",
            "Claim Investigation",
            "Complete Investigation",
            # The pendency sheet's own vocabulary. "Claim" alone is what most
            # of its rows say; DC is the agency's shorthand for death claim.
            "Claim",
            "DC",
            "DC Verification",
            "Health Claim",
            # A government life scheme, so still a death claim.
            "PMJJY",
            "PMJJBY",
            # Not investigations in themselves, but there is no separate form
            # for them and the sheet tracks them against the same case.
            "Document Procurement",
            "KOTAK:Runner Boy",
        ),
        default_tat_days=21,
        display_order=10,
    ),
    CaseTypeSeed(
        "DEATH_CLAIM_FTI",
        "Death Claim – Field Triggered Investigation",
        CaseCategory.DEATH_CLAIM,
        "Lighter field-triggered claim investigation (FTI).",
        ("FTI", "Field Triggered Investigation", "FTI Death Claim"),
        default_tat_days=14,
        display_order=20,
    ),
    CaseTypeSeed(
        "LANDLORD_VERIFICATION",
        "Landlord / Premises Risk Assessment",
        CaseCategory.DEATH_CLAIM,
        "Risk assessment of a proposed branch premises and its landlord.",
        (
            "Land lord",
            "Landlord",
            "Property Verification",
            "Premises Verification",
            "Risk Assessment",
        ),
        default_tat_days=10,
        display_order=30,
    ),
)


# --------------------------------------------------------------------------- #
# Import template — derived from the header strip in Image 3
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ColumnSeed:
    source_column: str
    target_field: str
    data_type: str = "text"
    is_required: bool = False
    aliases: tuple[str, ...] = ()
    notes: str = ""


IMPORT_COLUMNS: tuple[ColumnSeed, ...] = (
    ColumnSeed(
        "Co. Name",
        "company_code",
        "text",
        True,
        ("Company", "Company Name", "Insurer", "Co Name", "Client"),
    ),
    ColumnSeed(
        "Case Type", "case_type_code", "text", True, ("Type", "Case_Type", "Assignment Type")
    ),
    ColumnSeed("Month", "received_month", "text", False, ()),
    ColumnSeed(
        "Date",
        "received_at",
        "date",
        True,
        ("Received Date", "Allocation Date", "Assignment Date", "Case Date"),
    ),
    ColumnSeed("Aging", "aging_days", "int", False, ("Ageing", "Agi", "Age Days")),
    ColumnSeed(
        "KRN No",
        "krn_no",
        "text",
        False,
        ("KRN", "Key Reference Number", "KRN Number", "Reference No"),
    ),
    ColumnSeed(
        "Policy Number",
        "policy_number",
        "text",
        False,
        ("Policy No", "Policy No.", "Contract No", "Contract Number"),
    ),
    ColumnSeed(
        "Application Number",
        "application_number",
        "text",
        False,
        ("Application No", "Application No.", "App No", "Proposal No", "Application Numb"),
    ),
    ColumnSeed(
        "Life_Assured_Name",
        "life_assured_name",
        "text",
        True,
        ("Life Assured Name", "LA Name", "Insured Name", "Customer Name", "Name of LA"),
    ),
    ColumnSeed("City", "city", "text", False, ()),
    ColumnSeed("State", "state", "text", False, ()),
    ColumnSeed(
        "Assign To",
        "assigned_to",
        "text",
        False,
        ("Assigned To", "IO Name", "Investigator", "Allocated To"),
    ),
    ColumnSeed("Status", "status", "text", False, ("Case Status",)),
    ColumnSeed(
        "Remark/ADD IO ID",
        "import_remark",
        "text",
        False,
        ("Remark", "Remarks", "ADD IO ID", "Remark/ADD IO II"),
    ),
    ColumnSeed("Pin Code", "pin_code", "text", False, ("Pincode", "PIN", "Pin")),
    ColumnSeed("Report Date", "report_date", "date", False, ("Rep Date", "Rep. Date")),
    ColumnSeed(
        "Completion Date",
        "completion_date",
        "date",
        False,
        ("Completion Dt", "Closed Date", "Completion Da"),
    ),
    ColumnSeed(
        "Report Prep By",
        "report_prepared_by",
        "text",
        False,
        ("Report Prepared By", "Prepared By", "Report Prep B"),
    ),
    # Extras accepted when the client sends a wider file.
    ColumnSeed("Address", "address", "text", False, ("Full Address", "LA Address")),
    ColumnSeed(
        "Contact Number",
        "contact_number",
        "text",
        False,
        ("Mobile", "Mobile No", "Contact No", "Phone"),
    ),
    ColumnSeed(
        "Alternate Contact", "alternate_contact", "text", False, ("Alternate No", "Alt Contact")
    ),
    ColumnSeed("Email", "email_id", "text", False, ("Email ID", "E-mail")),
    ColumnSeed("Product", "product_name", "text", False, ("Product Name", "Plan")),
    ColumnSeed("Sum Assured", "sum_assured", "decimal", False, ("SA", "Sum_Assured")),
    ColumnSeed("Premium Amount", "premium_amount", "decimal", False, ("Premium",)),
    ColumnSeed(
        "RCD", "risk_commencement_date", "date", False, ("Risk Commencement Date", "Risk Comm Date")
    ),
    ColumnSeed("Nominee Name", "nominee_name", "text", False, ("Nominee",)),
    ColumnSeed("Nominee Relation", "nominee_relation", "text", False, ("Relation",)),
    ColumnSeed("Date of Death", "date_of_death", "date", False, ("DOD", "Death Date")),
    ColumnSeed("Place of Death", "place_of_death", "text", False, ()),
    ColumnSeed("Cause of Death", "cause_of_death", "text", False, ()),
    ColumnSeed("Claimant Name", "claimant_name", "text", False, ("Nominee/Claimant",)),
    ColumnSeed("Claimant Relation", "claimant_relation", "text", False, ()),
)

IMPORT_TEMPLATE_CODE = "VIPL_STANDARD_V1"
IMPORT_TEMPLATE_NAME = "VIPL standard daily file"
IMPORT_TEMPLATE_DESCRIPTION = (
    "The daily Excel/CSV received from the client, matching the column layout in "
    "the supplied sample (Image 3). Extra columns are accepted and ignored; "
    "missing optional columns are fine."
)

#: Primary duplicate key, then the fallback used when KRN is blank.
DUPLICATE_KEY = ["company_code", "krn_no"]
FALLBACK_DUPLICATE_KEY = [
    "company_code",
    "policy_number",
    "application_number",
    "life_assured_name",
]


# --------------------------------------------------------------------------- #
# Document templates: which supplied file belongs to which company + case type
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DocumentTemplateSeed:
    filename: str
    folder: str
    company_code: str
    case_type_code: str
    name: str
    notes: str = ""


DOCUMENT_TEMPLATES: tuple[DocumentTemplateSeed, ...] = (
    DocumentTemplateSeed(
        "Aditya Birla Life.docx",
        "investigation_docs",
        "ABSLI",
        "PRE_ISSUANCE",
        "Aditya Birla — Pre-Issuance Verification Report",
    ),
    DocumentTemplateSeed(
        "BAJAJ.docx",
        "investigation_docs",
        "BAJAJ",
        "PRE_ISSUANCE",
        "Bajaj Allianz — Detailed Verification Report (Confidential)",
    ),
    DocumentTemplateSeed(
        "BAXA.docx",
        "investigation_docs",
        "BAXA",
        "PRE_CLAIM",
        "Bharti AXA — Pre Claim Report",
    ),
    DocumentTemplateSeed(
        "Bandhan.docx",
        "investigation_docs",
        "BANDHAN",
        "PRE_ISSUANCE",
        "Bandhan Life — Pre Issuance Verification Report",
    ),
    DocumentTemplateSeed(
        "HDFC Profile check.docx",
        "investigation_docs",
        "HDFC",
        "PROFILE_CHECK",
        "HDFC Life — Pre-Claims Investigation Report",
    ),
    DocumentTemplateSeed(
        "HDFC Pre claim.doc",
        "investigation_docs",
        "HDFC",
        "PRE_CLAIM",
        "HDFC Life — Pre Claim Report",
        notes=(
            "Legacy Word 97-2003 binary .doc. Re-save it as .docx and upload a new "
            "version to enable DOCX generation; PDF generation works meanwhile."
        ),
    ),
    DocumentTemplateSeed(
        "HSBC Canera life.docx",
        "investigation_docs",
        "HSBC",
        "PRE_ISSUANCE",
        "Canara HSBC — Detailed Investigation Report",
    ),
    DocumentTemplateSeed(
        "HSBC Canara Mistry Shopping.docx",
        "investigation_docs",
        "HSBC",
        "MEDICAL_SEEDING",
        "Canara HSBC — Medical Seeding Report",
    ),
    DocumentTemplateSeed(
        "Icici Add.docx",
        "investigation_docs",
        "ICICI",
        "PROFILE_CHECK",
        "ICICI Prudential — Customer Profile Verification Form",
    ),
    DocumentTemplateSeed(
        "Icici Payout.docx",
        "investigation_docs",
        "ICICI",
        "PAYOUT_VERIFICATION",
        "ICICI Prudential — Payout Verification Form",
    ),
    DocumentTemplateSeed(
        "LMS.docx",
        "investigation_docs",
        "ICICI",
        "NEW_BUSINESS_VERIFICATION",
        "ICICI Prudential — Customer Verification Form (New Business)",
    ),
    DocumentTemplateSeed(
        "Kotak Life.docx",
        "investigation_docs",
        "KOTAK",
        "PRE_CLAIM",
        "Kotak Life — Detailed Investigation [Pre-Claims] Report",
    ),
    DocumentTemplateSeed(
        "Kotak Discreate Cheak.docx",
        "investigation_docs",
        "ICICI",
        "DISCREET_CHECK",
        "ICICI Prudential — Discreet Check Report",
    ),
    DocumentTemplateSeed(
        "PNB METLIFE.docx",
        "investigation_docs",
        "PNBMET",
        "PRE_CLAIM",
        "PNB MetLife — Scenario-Based Verification Report",
    ),
    DocumentTemplateSeed(
        "Bajaj death claim.docx",
        "death_claim_docs",
        "BAJAJ",
        "DEATH_CLAIM",
        "Bajaj Allianz — Death Claim Investigation Report",
    ),
    DocumentTemplateSeed(
        "HDFC Death Claim.docx",
        "death_claim_docs",
        "HDFC",
        "DEATH_CLAIM",
        "HDFC Life — Death Claim Investigation Report",
    ),
    DocumentTemplateSeed(
        "ICICI Death Claim.docx",
        "death_claim_docs",
        "ICICI",
        "DEATH_CLAIM",
        "ICICI Prudential — Claim Investigation Report",
    ),
    DocumentTemplateSeed(
        "FTI Icici.docx",
        "death_claim_docs",
        "ICICI",
        "DEATH_CLAIM_FTI",
        "ICICI Prudential — FTI Claim Investigation Report",
    ),
    DocumentTemplateSeed(
        "SUD Life.docx",
        "death_claim_docs",
        "SUD",
        "DEATH_CLAIM",
        "SUD Life — Investigation Report",
    ),
    DocumentTemplateSeed(
        "Land lord death claim.docx",
        "death_claim_docs",
        "ICICI",
        "LANDLORD_VERIFICATION",
        "ICICI Prudential — New Property Acquisition Risk Assessment",
    ),
)


# --------------------------------------------------------------------------- #
# HR masters
# --------------------------------------------------------------------------- #
DEPARTMENTS: tuple[tuple[str, str], ...] = (
    ("OPS", "Field Operations"),
    ("BACKOFF", "Back Office"),
    ("QC", "Quality Control"),
    ("HR", "Human Resources"),
    ("ADMIN", "Administration"),
)

DESIGNATIONS: tuple[tuple[str, str, str], ...] = (
    ("IO", "Investigating Officer", "G1"),
    ("SIO", "Senior Investigating Officer", "G2"),
    ("FE", "Field Executive", "G1"),
    ("TL", "Team Leader", "G3"),
    ("MGR", "Operations Manager", "G4"),
    ("QCEXEC", "QC Executive", "G2"),
    ("DEO", "Data Entry Operator", "G1"),
    ("HREXEC", "HR Executive", "G2"),
)
