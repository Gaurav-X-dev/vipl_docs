"""Seeded investigation form layouts, transcribed from the supplied .docx files.

Section titles and field labels are the client's own wording. See
``docs/ATTACHMENT_ANALYSIS.md`` §6.1 – §6.13 for the source of each block.
"""

from __future__ import annotations

from app.models.enums import FieldSource, FieldType
from app.seeds.form_dsl import (
    BANK,
    DOCUMENT_COLUMNS,
    EVIDENCE_STATUS,
    FAMILY_COLUMNS,
    FEEDBACK,
    HEALTH_STATUS,
    HOSPITAL_COLUMNS,
    HOUSE_TYPE,
    LOCALITY,
    MARITAL_STATUS,
    NARRATIVE,
    NEIGHBOUR_COLUMNS,
    OCCUPATION_TYPE,
    OTHER_POLICY_COLUMNS,
    OWNERSHIP,
    POSITIVE_NEGATIVE,
    PROPOSAL_MATCH_COLUMNS,
    STANDARD_OF_LIVING,
    TABLE,
    YES_NO,
    YES_NO_NA,
    F,
    S,
    T,
    agency_section,
    outcome_section,
    photographs_section,
    policy_section,
)

# --------------------------------------------------------------------------- #
# 6.1 Aditya Birla Sun Life — Pre-Issuance Verification Report
# --------------------------------------------------------------------------- #
ADITYA_BIRLA_PRE_ISSUANCE = T(
    code="ABSLI_PRE_ISSUANCE",
    name="Aditya Birla — Pre-Issuance Verification Report",
    company="ABSLI",
    case_type="PRE_ISSUANCE",
    source_document="investigation_docs/Aditya Birla Life.docx",
    sections=[
        S(
            "basic_information",
            "Basic Information",
            [
                BANK("policy_number", "Policy No.", "policy_number"),
                BANK("application_number", "Application No.", "application_number"),
                BANK("life_assured_name", "Name", "life_assured_name"),
                BANK(
                    "la_address",
                    "Address",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                BANK("contact_number", "Contact Number", "contact_number", type=FieldType.PHONE),
                F("alternate_address", "Alternate Address"),
                F(
                    "date_of_investigation",
                    "Date of Investigation",
                    type=FieldType.DATE,
                    required=True,
                    doc="date_of_visit",
                ),
            ],
        ),
        S(
            "residence_visit",
            "Residence Visit Details — Direct Check Details",
            [
                F("person_met", "Person Met", required=True, doc="person_met"),
                F("relation", "Relation", doc="relation_with_la"),
                F("period_of_stay", "Period of stay"),
                F(
                    "ownership_of_house",
                    "Ownership of House",
                    type=FieldType.SELECT,
                    options=OWNERSHIP,
                ),
                F("residence_type", "Residence Type", type=FieldType.SELECT, options=HOUSE_TYPE),
                F("locality", "Locality", type=FieldType.SELECT, options=LOCALITY),
                F("la_dob", "DOB", type=FieldType.DATE, doc="la_dob"),
                F("education", "Education", doc="la_qualification"),
                F(
                    "marital_status",
                    "Marital Status",
                    type=FieldType.SELECT,
                    options=MARITAL_STATUS,
                    doc="la_marital_status",
                ),
                F("family_members_count", "Family Members", type=FieldType.NUMBER),
                F("earning_members_count", "Earning Members", type=FieldType.NUMBER),
                F("occupation", "Occupation", doc="la_occupation"),
                F("income", "Income", doc="la_annual_income"),
                F(
                    "neighbors_confirmation",
                    "Neighbors Confirmation",
                    type=FieldType.SELECT,
                    options=FEEDBACK,
                ),
                F("negative_habits", "Negative Habits — If any"),
                F(
                    "overall_health",
                    "Overall, Health",
                    type=FieldType.SELECT,
                    options=HEALTH_STATUS,
                ),
                F("negative_information", "Negative Information — If any"),
                NARRATIVE("fe_remarks", "FE Remarks", doc="overall_remarks"),
            ],
        ),
        S(
            "vicinity_summary",
            "Discreet / Vicinity Check — Summary",
            [
                NARRATIVE(
                    "nearby_reference",
                    "Nearby shop/office for reference — name / designation / contact details",
                ),
                F(
                    "financial_standing",
                    "Financial Standing of the Life Assured",
                    type=FieldType.SELECT,
                    options=STANDARD_OF_LIVING,
                    doc="standard_of_living",
                ),
                F("overall_feedback", "Overall feedback", type=FieldType.SELECT, options=FEEDBACK),
                F("negative_feedback", "Negative feedback (if any)"),
                F(
                    "disparity_noted",
                    "Any disparity noted between vicinity check results vs direct check results",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                NARRATIVE("vicinity_remarks", "Vicinity check narrative", doc="vicinity_remarks"),
            ],
        ),
        S(
            "report_prepared_by",
            "Report Prepared by",
            [
                F(
                    "verification_agency",
                    "Verification agency name and code",
                    doc="agency_name",
                    default="Virtual007",
                ),
                F(
                    "field_executive_name",
                    "Field executive name",
                    prefill="assigned_to_name",
                    doc="field_investigator_name",
                ),
            ],
        ),
        outcome_section(with_report_status=False),
        photographs_section(
            ["Life Assured photograph", "Residence photograph", "Vicinity photograph"]
        ),
    ],
)


# --------------------------------------------------------------------------- #
# 6.2 Bajaj Allianz — Detailed Verification Report (Confidential)
# --------------------------------------------------------------------------- #
def _bajaj_profile_row(
    key: str, label: str, prefill: str | None = None
) -> list[F]:
    """Each Bajaj profile row is value / matches proposal / output.

    ``prefill`` names the case column the row already knows, so what the
    client sent is on the form (and in the report) without anyone retyping it.
    """
    return [
        F(f"{key}_value", label, col_span=6, prefill=prefill),
        F(
            f"{key}_match",
            f"{label} — matching with proposal form",
            type=FieldType.SELECT,
            options=YES_NO_NA,
            col_span=3,
        ),
        F(
            f"{key}_output",
            f"{label} — output",
            type=FieldType.SELECT,
            options=["Positive", "Negative", "NA"],
            col_span=3,
        ),
    ]


_BAJAJ_PROFILE_FIELDS: list[F] = []
for _key, _label, _prefill in (
    ("spoke_with", "Spoke with", None),
    ("la_name", "Life Assured Name", "life_assured_name"),
    ("dob_age", "DOB / Age", None),
    ("place_of_birth", "Place of Birth", None),
    ("marital_status", "Marital Status", None),
    ("education", "Education Qualification", None),
    ("occupation_type", "Occupation Type", None),
    ("income", "Income / Salary (Per Annum)", None),
    ("employer", "Employer Name / Trade Name", None),
    ("other_insurance", "Other Life or Health Insurance", None),
    ("other_insurance_details", "Details of other Insurance", None),
):
    _BAJAJ_PROFILE_FIELDS.extend(_bajaj_profile_row(_key, _label, _prefill))

BAJAJ_PRE_ISSUANCE = T(
    code="BAJAJ_PRE_ISSUANCE",
    name="Bajaj Allianz — Detailed Verification Report (Confidential)",
    company="BAJAJ",
    case_type="PRE_ISSUANCE",
    source_document="investigation_docs/BAJAJ.docx",
    sections=[
        S(
            "header",
            "Detailed Verification Report (Confidential)",
            [
                F(
                    "agency_name",
                    "Investigation agency name",
                    doc="agency_name",
                    default="Virtual Investigation Services",
                ),
                F(
                    "investigation_type",
                    "Investigation type",
                    type=FieldType.SELECT,
                    options=["Live Insurance", "Non-Live", "Health"],
                ),
                BANK(
                    "application_policy_number",
                    "Application number / policy number",
                    "policy_number",
                    doc="policy_number",
                ),
                BANK(
                    "case_entrusted_date",
                    "Case entrusted date",
                    "received_at",
                    type=FieldType.DATE,
                    doc="case_entrusted_date",
                ),
                F(
                    "date_of_verification",
                    "Date of verification",
                    type=FieldType.DATE,
                    required=True,
                    doc="date_of_visit",
                ),
                F(
                    "time_of_investigation",
                    "Time of investigation",
                    type=FieldType.TIME,
                    doc="time_of_visit",
                ),
                F(
                    "report_submission_date",
                    "Report submission date",
                    type=FieldType.DATE,
                    doc="report_submission_date",
                ),
                F(
                    "verification_done_with",
                    "Verification done with",
                    required=True,
                    doc="person_met",
                ),
            ],
        ),
        S("profile_of_la", "(A) Profile of LA", _BAJAJ_PROFILE_FIELDS),
        S(
            "habits_health",
            "(B) Habits & Health of Life Assured",
            [
                F("smoking", "Smoking", type=FieldType.SELECT, options=YES_NO_NA),
                F(
                    "smoking_details",
                    "If Yes: how many cigarettes per day and since how many years",
                ),
                F("drinking", "Drinking", type=FieldType.SELECT, options=YES_NO_NA),
                F("drinking_details", "If Yes: frequency, quantity in ML and since how long"),
                F(
                    "hospitalised_3_years",
                    "LA hospitalised in the last 3 years",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                NARRATIVE(
                    "hospitalisation_details",
                    "Detailed information with reason (surgery / accident / delivery)",
                ),
                F("family_physician", "Family physician details if any"),
            ],
        ),
        S(
            "medication_status",
            "(C) Medication status",
            [
                F(
                    "under_treatment",
                    "Is the customer taking any medicines / under treatment?",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                NARRATIVE("medication_details", "If yes, details of medication"),
            ],
        ),
        S(
            "family_details",
            "(D) Family Details (as per Investigation)",
            [
                F("family_members_relation", "Family members count & relation"),
                F("dependents_count", "No. of dependents", type=FieldType.NUMBER),
                F("total_family_income", "Total family income"),
                F("family_health_history", "Family health history"),
                F("family_policies", "Family life / health policy"),
                F("political_relation", "Political relation"),
                TABLE("family_members", "Family members", FAMILY_COLUMNS, doc="family_members"),
            ],
        ),
        S(
            "important_details",
            "(E) Important Details (As per Proposal Form)",
            [
                BANK("contact_numbers", "Contact no. & alternate no.", "contact_number"),
                F("email_ids", "Email ID / alternate email ID", type=FieldType.EMAIL),
                BANK(
                    "permanent_address",
                    "Permanent address",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                F(
                    "communication_address",
                    "Communication address",
                    type=FieldType.TEXTAREA,
                    col_span=12,
                ),
                F(
                    "type_of_address",
                    "Type of address",
                    type=FieldType.SELECT,
                    options=["Residence", "Office", "Both", "Not shared"],
                ),
                F("nominee_details", "Nominee name / relation / contact no.", doc="nominee_name"),
                F("nominee_dob", "Nominee DOB", type=FieldType.DATE, doc="nominee_dob"),
                F("nominee_occupation_income", "Nominee occupation & income"),
                F("sum_assured_premium", "Sum assured, premium amount / mode"),
                F("policy_term_ppt", "Policy term & premium paying term"),
                F("premium_payer", "Who is paying the premium"),
            ],
        ),
        S(
            "other_observations",
            "(F) Other Observations",
            [
                F("face_match_score", "Face matching score with proposal form"),
                NARRATIVE("vicinity_remarks", "Vicinity check", doc="vicinity_remarks"),
                NARRATIVE("overall_remarks", "Overall observations", doc="overall_remarks"),
            ],
        ),
        outcome_section(),
        photographs_section(["LA photograph", "Residence photograph", "KYC documents"]),
    ],
)


# --------------------------------------------------------------------------- #
# 6.3 Bharti AXA — Pre Claim Report
# --------------------------------------------------------------------------- #
BAXA_PRE_CLAIM = T(
    code="BAXA_PRE_CLAIM",
    name="Bharti AXA — Pre Claim Report",
    company="BAXA",
    case_type="PRE_CLAIM",
    source_document="investigation_docs/BAXA.docx",
    sections=[
        S(
            "brief_details",
            "Brief Details (as per company)",
            [
                F(
                    "type_of_claim",
                    "Type of claim",
                    default="Pre Claim",
                    type=FieldType.SELECT,
                    options=["Pre Claim", "Death Claim", "Health Claim"],
                ),
                BANK("life_assured_name", "Life Insured Mr. / Mrs. / Ms.", "life_assured_name"),
                BANK("policy_number", "Policy no", "policy_number"),
                F("la_age", "Age (or DOB)", doc="la_age"),
                BANK(
                    "la_address",
                    "Address",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                BANK(
                    "date_of_policy",
                    "Date of Policy",
                    "risk_commencement_date",
                    type=FieldType.DATE,
                    doc="rcd",
                ),
                F(
                    "report_submission_date",
                    "Report Submission Date",
                    type=FieldType.DATE,
                    doc="report_submission_date",
                ),
            ],
        ),
        S(
            "questionnaire",
            "Detailed Report",
            [
                F(
                    "q1_traceable",
                    "1. Is LA and his family traceable at the given address?",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    required=True,
                    col_span=12,
                ),
                F(
                    "q2_alive_healthy",
                    "2. Is Life Assured alive? If yes, is he healthy and well?",
                    col_span=12,
                ),
                F(
                    "q3_condition_justifies",
                    "3. Was the condition (financial and health both) of LA justifying the insurance?",
                    col_span=12,
                ),
                F(
                    "q4_age_as_proposed",
                    "4. Is the age of LA as proposed?",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                    col_span=12,
                ),
                NARRATIVE("q5_notable_findings", "5. Are there any other notable findings?"),
                NARRATIVE("q6_hospital_checks", "6. Details of hospital checks"),
                TABLE("hospitals", "Hospital / chemist checks", HOSPITAL_COLUMNS, doc="hospitals"),
            ],
        ),
        S(
            "detailed_finding",
            "Detailed Finding",
            [
                NARRATIVE("vicinity_remarks", "Vicinity Check", doc="vicinity_remarks"),
                NARRATIVE("overall_remarks", "Overall Observation", doc="overall_remarks"),
            ],
        ),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.4 Bandhan Life — Pre Issuance Verification Report
# --------------------------------------------------------------------------- #
BANDHAN_PRE_ISSUANCE = T(
    code="BANDHAN_PRE_ISSUANCE",
    name="Bandhan Life — Pre Issuance Verification Report",
    company="BANDHAN",
    case_type="PRE_ISSUANCE",
    source_document="investigation_docs/Bandhan.docx",
    sections=[
        S(
            "header",
            "Pre Issuance Verification Report",
            [
                F(
                    "report_type",
                    "Report Type",
                    type=FieldType.SELECT,
                    options=["Interim", "Final"],
                    default="Final",
                    doc="report_status",
                ),
                F(
                    "investigation_date",
                    "Investigation Date",
                    type=FieldType.DATE,
                    required=True,
                    doc="date_of_visit",
                ),
                BANK("application_number", "Application No", "application_number"),
                BANK("rcd", "RCD", "risk_commencement_date", type=FieldType.DATE, doc="rcd"),
                BANK(
                    "inv_received_date",
                    "INV Received Date",
                    "received_at",
                    type=FieldType.DATE,
                    doc="assignment_date",
                ),
                F(
                    "report_sent_date",
                    "Report Sent Date",
                    type=FieldType.DATE,
                    doc="report_submission_date",
                ),
            ],
        ),
        S(
            "life_assured",
            "Life Assured details",
            [
                BANK("life_assured_name", "Name of Life Assured", "life_assured_name"),
                BANK(
                    "company_provided_address",
                    "Company Provided Address",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                BANK(
                    "contact_number",
                    "Contact No / Alternate No",
                    "contact_number",
                    type=FieldType.PHONE,
                ),
                F(
                    "la_met_in_person",
                    "LA Met in person",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    required=True,
                ),
                F("date_of_death", "If died, DOD", type=FieldType.DATE, doc="date_of_death"),
                F(
                    "existence_of_address",
                    "Existence of Address",
                    type=FieldType.SELECT,
                    options=["Confirmed", "Not confirmed"],
                ),
                F(
                    "existence_of_la",
                    "Existence of LA",
                    type=FieldType.SELECT,
                    options=["Confirmed", "Not confirmed"],
                ),
                F("la_dob", "Date of Birth", type=FieldType.DATE, doc="la_dob"),
                F("qualification", "Qualification", doc="la_qualification"),
                F(
                    "occupation",
                    "Occupation",
                    type=FieldType.SELECT,
                    options=OCCUPATION_TYPE,
                    doc="la_occupation",
                ),
                F("nature_of_work", "Nature of Work"),
                F("employer_name", "Name of Employer"),
                F("income", "Income", doc="la_annual_income"),
                F(
                    "standard_of_living",
                    "Standard of Living",
                    type=FieldType.SELECT,
                    options=STANDARD_OF_LIVING,
                    doc="standard_of_living",
                ),
                F(
                    "health_condition",
                    "Health Condition",
                    type=FieldType.SELECT,
                    options=HEALTH_STATUS,
                ),
                F("negative_habits", "Negative Habits"),
                F("pre_existing_illness", "Pre Existing illness"),
                F("call_history", "Call History"),
                F(
                    "evidence_collected",
                    "Evidence collected",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "audio_video_confirmation",
                    "Audio / Video Confirmation",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "geo_photo",
                    "Location Photo with Geo tagging",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "existing_policy_details",
                    "Existing policy details",
                    type=FieldType.TEXTAREA,
                    col_span=12,
                ),
            ],
        ),
        S(
            "findings",
            "Findings",
            [
                NARRATIVE("vicinity_remarks", "Vicinity Findings", doc="vicinity_remarks"),
                NARRATIVE("overall_remarks", "Overall Findings", doc="overall_remarks"),
                NARRATIVE("summary_of_findings", "Summary of Findings"),
                F(
                    "final_remark",
                    "Investigation Final Remark",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                    required=True,
                    doc="outcome",
                ),
            ],
        ),
        S(
            "sign_off",
            "Declaration and sign-off",
            [
                F("verification_agency", "Verification agency & owner name", doc="agency_name"),
                F(
                    "field_officer_details",
                    "Field officer details",
                    prefill="assigned_to_name",
                    doc="field_investigator_name",
                ),
                F("declaration_date", "Date", type=FieldType.DATE),
                F(
                    "declaration_accepted",
                    "I declare the statements and information above are true and complete",
                    type=FieldType.BOOLEAN,
                    required=True,
                    col_span=12,
                ),
            ],
        ),
        photographs_section(
            ["Photograph with geo tagging (latitude and longitude)", "KYC documents"]
        ),
    ],
)


# --------------------------------------------------------------------------- #
# 6.5 HDFC Life — Pre-Claims Investigation Report (Profile check)
# --------------------------------------------------------------------------- #
def _yes_no_with_detail(key: str, label: str, detail_label: str) -> list[F]:
    return [
        F(key, label, type=FieldType.SELECT, options=YES_NO_NA, col_span=4),
        F(f"{key}_details", detail_label, type=FieldType.TEXTAREA, col_span=8),
    ]


_HDFC_PERSONAL: list[F] = []
for _k, _l, _d in (
    (
        "address_traceable",
        "Is the Address Traceable?",
        "If No: where did LA meet, and why not at the KYC address?",
    ),
    (
        "la_met",
        "Did the LA meet?",
        "If No: LA Expired / Not traceable / Refused to meet / Works elsewhere / "
        "Not at home / Shifted / At work",
    ),
    ("la_salaried", "Is the LA Salaried?", "If Yes: company name, designation, income per annum"),
    (
        "la_self_employed",
        "Is the LA Self Employed?",
        "If Yes: business registration name, owner name, income per annum",
    ),
    (
        "la_healthy",
        "Does the LA look healthy?",
        "If No: specify the adversity noted; medical records / declaration to be collected",
    ),
    ("la_alcohol", "Does LA consume Alcohol?", "If Yes: what is the quantity? Collect declaration"),
    (
        "la_educated",
        "Is the LA educated?",
        "If Yes: highest qualification; proof / declaration to be collected",
    ),
    (
        "met_family_member",
        "Did you meet any family member?",
        "Name of the person met and their relation with the LA",
    ),
):
    _HDFC_PERSONAL.extend(_yes_no_with_detail(_k, _l, _d))

_HDFC_IDENTIFICATION: list[F] = []
for _k, _l, _d in (
    (
        "la_identified",
        "Is the LA Identified?",
        "If Yes: is LA a tenant or owner of the address, and since when residing there?",
    ),
    ("la_alive", "Is the LA alive?", "If No: what is the cause of death?"),
    (
        "health_adversity",
        "Any adversity on health?",
        "If Yes: what adversity, since when, and where was treatment taken?",
    ),
    (
        "adverse_habit",
        "Is there any adverse habit identified?",
        "Alcohol / smoking / drug or substance abuse — quantity and frequency",
    ),
    (
        "salaried_confirm",
        "Is the LA Salaried?",
        "If Yes: where does he work and estimated income per year?",
    ),
    (
        "self_employed_confirm",
        "Is the LA self-employed?",
        "If Yes: nature of business, is the LA the owner, estimated income per year?",
    ),
):
    _HDFC_IDENTIFICATION.extend(_yes_no_with_detail(_k, _l, _d))

HDFC_PROFILE_CHECK = T(
    code="HDFC_PROFILE_CHECK",
    name="HDFC Life — Pre-Claims Investigation Report",
    company="HDFC",
    case_type="PROFILE_CHECK",
    source_document="investigation_docs/HDFC Profile check.docx",
    sections=[
        agency_section(),
        S(
            "investigation_outcome",
            "Investigation Outcome",
            [
                BANK(
                    "policy_application_number",
                    "Policy Number / Application Number",
                    "policy_number",
                ),
                F(
                    "outcome",
                    "Outcome (Positive / Negative / Suspicious)",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                    required=True,
                    doc="outcome",
                ),
                F(
                    "outcome_specify",
                    "Please specify",
                    type=FieldType.SELECT,
                    col_span=12,
                    options=[
                        "Life Existed",
                        "Non Existed",
                        "Terminally Ill or older lives",
                        "Death Before Issuance",
                        "Third party Investments / Financially very poor profile",
                        "Non Disclosure",
                        "Non contactable",
                        "Others",
                    ],
                    doc="outcome_reason",
                ),
            ],
        ),
        S(
            "policy_proposal_details",
            "Policy / Proposal Details",
            [
                BANK("life_assured_name", "LA Name", "life_assured_name"),
                F("la_dob", "LA DOB", type=FieldType.DATE, doc="la_dob"),
                BANK(
                    "la_address",
                    "Address",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
            ],
        ),
        S("personal_details", "Personal Details of the Insured", _HDFC_PERSONAL),
        S(
            "vicinity_check",
            "Vicinity Check",
            [
                NARRATIVE(
                    "vicinity_remarks",
                    "Discussion and conclusion from relatives / neighbourhood / nearby houses",
                    doc="vicinity_remarks",
                ),
                TABLE(
                    "neighbours",
                    "Persons met during the vicinity check",
                    NEIGHBOUR_COLUMNS,
                    doc="neighbours",
                ),
            ],
        ),
        S("identification", "Identification and confirmation", _HDFC_IDENTIFICATION),
        S(
            "agency_findings",
            "Investigation Agency Overall Findings",
            [NARRATIVE("overall_remarks", "Overall findings", doc="overall_remarks")],
        ),
        S(
            "documents_procured",
            "Documents Procured / Collected",
            [
                F("doc_age_proof", "Age Proof", type=FieldType.SELECT, options=EVIDENCE_STATUS),
                F(
                    "doc_income_proof",
                    "Occupation and Income Proof",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "doc_live_photo",
                    "Customer live photo with house photo",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "doc_medical",
                    "Medical Evidence — if any",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "doc_nominee_kyc",
                    "Nominee KYC (age / identity / photo)",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "doc_death_certificate",
                    "If LA expired: death certificate and Anganwadi certificate",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "doc_declarations",
                    "All declarations collected with the LA photo",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                TABLE(
                    "documents_collected",
                    "Documents collected",
                    DOCUMENT_COLUMNS,
                    doc="documents_collected",
                ),
            ],
            description="Photographs must be submitted with location tagging plus a date and time stamp.",
        ),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.6 Canara HSBC — Detailed Investigation Report
# --------------------------------------------------------------------------- #
HSBC_PRE_ISSUANCE = T(
    code="HSBC_PRE_ISSUANCE",
    name="Canara HSBC — Detailed Investigation Report",
    company="HSBC",
    case_type="PRE_ISSUANCE",
    source_document="investigation_docs/HSBC Canera life.docx",
    sections=[
        S(
            "case_header",
            "Detailed Investigation Report",
            [
                BANK(
                    "proposal_number",
                    "Proposal No.",
                    "application_number",
                    doc="application_number",
                ),
                BANK("life_assured_name", "Life Assured Name", "life_assured_name"),
                BANK(
                    "allocation_date",
                    "Allocation date",
                    "received_at",
                    type=FieldType.DATE,
                    doc="allocation_date",
                ),
                F(
                    "verification_type",
                    "Verification Type",
                    type=FieldType.SELECT,
                    options=["Direct Visit", "Discreet", "Telephonic", "Video call"],
                ),
                BANK(
                    "la_address",
                    "Address (complete address)",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                BANK("contact_number", "Mobile No.", "contact_number", type=FieldType.PHONE),
                F("alternate_contact", "Alternate number / email ID if given"),
                F(
                    "verification_date",
                    "Verification date",
                    type=FieldType.DATE,
                    required=True,
                    doc="date_of_visit",
                ),
                F(
                    "report_overall_status",
                    "Report Overall Status",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                    required=True,
                    doc="outcome",
                ),
                F(
                    "verifier_name",
                    "Verifier Name",
                    prefill="assigned_to_name",
                    doc="field_investigator_name",
                ),
            ],
        ),
        S(
            "observations",
            "Observations of the Investigators",
            [
                F("id_card_seen", "ID card seen — name of ID proof with complete number"),
                F("address_proof_seen", "Address proof seen — name of proof with complete number"),
                F(
                    "person_met",
                    "Name of person met (name & mobile no.)",
                    required=True,
                    doc="person_met",
                ),
                F("met_person_relation", "Met person relation with LA", doc="relation_with_la"),
                F("la_dob", "LA date of birth", type=FieldType.DATE, doc="la_dob"),
                NARRATIVE(
                    "health_lifestyle",
                    "LA health condition and lifestyle (tobacco / alcohol / smoking / "
                    "swimming / diving etc.)",
                ),
                NARRATIVE(
                    "disease_details",
                    "If LA not healthy — name of disease, duration, place of treatment "
                    "(hospital and doctor name)",
                ),
                NARRATIVE(
                    "medical_history",
                    "Any history of medical investigation, surgery or treatment in the "
                    "past or planned in the near future",
                ),
                NARRATIVE("family_medical_history", "Family medical history"),
                F(
                    "treatment_papers",
                    "Treatment papers / audio / video captured",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "other_policies",
                    "Policy details other than Canara HSBC and total life coverage",
                    type=FieldType.TEXTAREA,
                    col_span=12,
                ),
                F(
                    "residence_locality",
                    "Residence locality and type",
                    type=FieldType.SELECT,
                    options=LOCALITY,
                ),
                F(
                    "residence_ownership",
                    "Residence ownership",
                    type=FieldType.SELECT,
                    options=OWNERSHIP,
                ),
                F("years_at_residence", "No. of years at current residence"),
                F(
                    "financial_status",
                    "Financial status of Life Assured",
                    type=FieldType.SELECT,
                    options=STANDARD_OF_LIVING,
                    doc="standard_of_living",
                ),
                NARRATIVE("family_members_details", "No. of family members and their details"),
                F(
                    "education_qualification",
                    "LA's education qualification",
                    doc="la_qualification",
                ),
                F(
                    "employment_category",
                    "Employment category (salaried / self-employed)",
                    type=FieldType.SELECT,
                    options=OCCUPATION_TYPE,
                    doc="la_occupation",
                ),
                F(
                    "organization_name",
                    "Organisation name (employer) and nature of work (if salaried)",
                ),
                F("self_employed_details", "Self employed (firm name, business type and address)"),
                F("annual_income", "Annual income", doc="la_annual_income"),
                F("nominee_details", "Nominee name and relationship with LA", doc="nominee_name"),
                NARRATIVE(
                    "vicinity_persons_details",
                    "Vicinity check details — met person name / mobile number",
                ),
            ],
        ),
        S(
            "narratives",
            "Findings",
            [
                NARRATIVE("discreet_check", "Discreet Check", doc="vicinity_remarks"),
                NARRATIVE("residence_visit", "Residence Visit"),
                NARRATIVE("health_and_habits", "Health and Habits"),
                NARRATIVE("family_details", "Family Details"),
                NARRATIVE(
                    "investigation_findings", "Investigation Findings", doc="overall_remarks"
                ),
                NARRATIVE("closing_note", "Note", doc="conclusion"),
            ],
        ),
        photographs_section(
            [
                "Photo of LA house with geo tagging",
                "Photo of LA or met person with geo tagging",
                "Photo of LA's KYC with geo tagging",
                "Field executive selfie with geo tagging",
            ]
        ),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.7 Canara HSBC — Medical Seeding Report (mystery shopping)
# --------------------------------------------------------------------------- #
_SEEDING_QUESTIONS: list[tuple[str, str, list[str]]] = [
    ("identified_at_reception", "Are you properly identified at the reception?", YES_NO),
    ("authorisation_checked", "Have they checked your authorisation letter and photo ID?", YES_NO),
    (
        "reception_response",
        "How was the response at the reception?",
        ["Excellent", "Good", "Average", "Poor"],
    ),
    (
        "time_to_attend",
        "How much time did it take to attend any of the medicals?",
        ["05 min", "15 Minutes", "30 Minutes", "1 Hour", "2 Hours"],
    ),
    ("left_unattended", "Were you left unattended?", YES_NO),
    ("lab_ambience", "How is the lab ambience?", ["Excellent", "Good", "Average", "Poor"]),
    ("sample_collection_room", "Does the DC have a proper sample collection room?", YES_NO),
    ("qualified_technician", "Has the blood been drawn by a qualified technician?", YES_NO_NA),
    ("disposable_syringes", "Is he using disposable syringes?", YES_NO_NA),
    ("marked_containers", "Is the blood sample transferred to marked containers?", YES_NO_NA),
    (
        "mbbs_performed_mer",
        "Did a qualified doctor (at least MBBS) perform the MER and ask valid "
        "medical-related questions?",
        YES_NO,
    ),
    (
        "doctor_offered_inducement",
        "Did the doctor assure conversion of a negative report to positive after some inducement?",
        YES_NO,
    ),
    ("couch_clean", "Is the examination couch clean?", YES_NO),
    ("bp_readings_taken", "Has he taken the BP readings?", YES_NO_NA),
    ("who_measured", "Who is doing the measurements?", ["Doctor", "Technician", "Other staff"]),
    ("readings_revealed", "Are the readings revealed to you?", YES_NO),
    ("report_copy_given", "Request them for a copy of the reports", YES_NO),
    ("weight_machine_maintained", "Is the weight machine properly maintained?", YES_NO),
    ("height_weight_measured", "Are the height and weight properly measured?", YES_NO),
    ("toilets_clean", "Are the toilets clean?", YES_NO),
    (
        "informed_to_leave",
        "Were you informed to leave, intimating that all the tests are over?",
        YES_NO,
    ),
]

_SEEDING_ACTIVITY: list[tuple[str, str]] = [
    ("height_measured", "Height measured"),
    ("weight_measured", "Weight measured"),
    ("chest_inspiration", "Chest inspirations"),
    ("chest_expiration", "Chest expirations"),
    ("blood_sample_given", "Blood sample given"),
    ("mixed_water_urine", "Mixed water in urine sample"),
    ("declared_alcoholic", "Declared alcoholic"),
    ("declared_smoker", "Declared smoker"),
    ("declared_other_medical", "Declared any other medical suffering"),
]

HSBC_MEDICAL_SEEDING = T(
    code="HSBC_MEDICAL_SEEDING",
    name="Canara HSBC — Medical Seeding Report",
    company="HSBC",
    case_type="MEDICAL_SEEDING",
    source_document="investigation_docs/HSBC Canara Mistry Shopping.docx",
    sections=[
        S(
            "seeding_header",
            "Medical Seeding Report",
            [
                F(
                    "date_of_seeding",
                    "Date of the seeding",
                    type=FieldType.DATE,
                    required=True,
                    doc="date_of_visit",
                ),
                F("medical_centre_name", "Name of the medical centre", required=True, col_span=12),
                F("location", "Location", prefill="city"),
                F(
                    "category_of_medical",
                    "Category of medical done",
                    help="For example: CAT-2 (MER, FBS, LIP, RUA), ECG",
                    col_span=12,
                ),
                F(
                    "seed_individual_name",
                    "Name of the individual who has gone for the medical",
                    col_span=12,
                ),
                F("organiser_name", "Name of the individual who organised the medical"),
            ],
        ),
        S(
            "questionnaire",
            "Mystery shopping observations",
            [
                F(key, label, type=FieldType.SELECT, options=options, col_span=6)
                for key, label, options in _SEEDING_QUESTIONS
            ],
            description=("Completed by the seeded candidate immediately after the visit."),
        ),
        S(
            "seeder_details",
            "Seeder details",
            [
                F("seed_name", "Seed name", required=True),
                F("seed_father_name", "Father's name"),
                F("seed_dob", "DOB", type=FieldType.DATE),
            ],
        ),
        S(
            "medical_activity",
            "Medical activity details",
            [
                item
                for key, label in _SEEDING_ACTIVITY
                for item in (
                    F(key, label, type=FieldType.SELECT, options=YES_NO, col_span=4),
                    F(f"{key}_reading", f"{label} — reading / remarks", col_span=8),
                )
            ],
        ),
        S(
            "family_history",
            "Family History",
            [
                TABLE(
                    "family_members",
                    "Family history",
                    [
                        {"key": "member", "label": "Family member"},
                        {"key": "status", "label": "Living / Dead"},
                        {"key": "age", "label": "Age"},
                        {"key": "health_status", "label": "Health status"},
                        {"key": "age_at_death", "label": "Age at death"},
                        {"key": "cause_of_death", "label": "Cause of death"},
                        {"key": "year_of_death", "label": "Year of death"},
                    ],
                    doc="family_members",
                )
            ],
        ),
        S(
            "observations",
            "Any other observations",
            [
                NARRATIVE("overall_remarks", "Observations", doc="overall_remarks"),
                NARRATIVE("closing_note", "Note / basis of closure", doc="conclusion"),
            ],
        ),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.8 ICICI Prudential — Customer profile verification form
# --------------------------------------------------------------------------- #
ICICI_PROFILE_CHECK = T(
    code="ICICI_PROFILE_CHECK",
    name="ICICI Prudential — Customer Profile Verification Form",
    company="ICICI",
    case_type="PROFILE_CHECK",
    source_document="investigation_docs/Icici Add.docx",
    sections=[
        S(
            "assignment",
            "Assignment",
            [
                BANK(
                    "assignment_date",
                    "Assignment date",
                    "received_at",
                    type=FieldType.DATE,
                    doc="assignment_date",
                ),
                F("agency_name", "Agency name", doc="agency_name"),
                F("agency_contact", "Contact number", type=FieldType.PHONE, doc="agency_contact"),
                F(
                    "report_submission_date",
                    "Report submission date",
                    type=FieldType.DATE,
                    doc="report_submission_date",
                ),
                F(
                    "decision",
                    "Decision",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                    required=True,
                    doc="outcome",
                ),
                F("la_met", "LA met", type=FieldType.SELECT, options=YES_NO),
                F(
                    "evidence_available",
                    "Evidence available",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F("evidence_details", "Evidence details", col_span=12),
                NARRATIVE("decision_remarks", "Remarks"),
            ],
        ),
        S(
            "policy_details",
            "Policy details",
            [
                BANK("application_number", "Application no.", "application_number"),
                BANK("policy_number", "Policy no", "policy_number"),
                F("issue_date", "Issue date", type=FieldType.DATE),
                BANK("product_name", "Product", "product_name"),
                BANK("sum_assured", "Sum assured", "sum_assured", type=FieldType.CURRENCY),
                BANK("premium_amount", "Premium amount", "premium_amount", type=FieldType.CURRENCY),
            ],
        ),
        S(
            "case_details",
            "Case details",
            [
                F("proposer_name", "Name of Proposer (PR)"),
                BANK("life_assured_name", "Name of Life Assured (LA)", "life_assured_name"),
                BANK(
                    "communication_address",
                    "Communication address",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                F("permanent_address", "Permanent address", type=FieldType.TEXTAREA, col_span=12),
                BANK("contact_number", "Contact number", "contact_number", type=FieldType.PHONE),
            ],
        ),
        S(
            "proposal_verification",
            "Proposal verification",
            [
                F("locality_of_la", "Locality of LA", type=FieldType.SELECT, options=LOCALITY),
                F(
                    "existence_established",
                    "Existence of LA established",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F("was_la_met", "Was LA met", type=FieldType.SELECT, options=YES_NO),
                F("whom_did_you_meet", "If LA not met, whom did you meet", doc="person_met"),
                F(
                    "relationship_with_la",
                    "If family, relationship with LA",
                    doc="relation_with_la",
                ),
                F("la_dob", "Date of birth of LA", type=FieldType.DATE, doc="la_dob"),
                F(
                    "identity_proof",
                    "Identity proof of LA",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "address_proof",
                    "Address proof of LA",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F("education", "Education of LA", doc="la_qualification"),
                F(
                    "health_details",
                    "Health details of LA",
                    type=FieldType.SELECT,
                    options=HEALTH_STATUS,
                ),
                F("habits", "Habits of LA"),
                F("habits_quantity", "Quantity / no. of years"),
                F("physical_appearance", "Physical appearance of LA"),
                F("handicapped", "If handicapped, then", type=FieldType.SELECT, options=YES_NO),
                F(
                    "existing_insurance",
                    "Existing insurance of LA",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                F("live_photo", "Live photo of LA", type=FieldType.SELECT, options=EVIDENCE_STATUS),
                F(
                    "residence_photo",
                    "Photo of residence of LA",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
            ],
        ),
        S(
            "proposer_details",
            "Proposer details",
            [
                F(
                    "occupation",
                    "Occupation",
                    type=FieldType.SELECT,
                    options=OCCUPATION_TYPE,
                    doc="la_occupation",
                ),
                F("company_name", "Name of company"),
                F("income", "Income", doc="la_annual_income"),
                F("income_proof", "Income proof", type=FieldType.SELECT, options=EVIDENCE_STATUS),
                F("family_members_count", "Number of members in family", type=FieldType.NUMBER),
                F(
                    "earning_members_count",
                    "Number of earning members in family",
                    type=FieldType.NUMBER,
                ),
                F(
                    "office_shop_photo",
                    "Photo of office / shop",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F("house_type", "Type of house", type=FieldType.SELECT, options=HOUSE_TYPE),
            ],
        ),
        S(
            "vicinity_check",
            "Vicinity check",
            [
                F("vicinity_education", "Education of LA as per vicinity"),
                F("vicinity_health", "Health details of LA as per vicinity"),
                F("vicinity_habits", "Habits of LA as per vicinity"),
                F("vicinity_appearance", "Physical appearance as per vicinity"),
                F(
                    "vicinity_years_at_address",
                    "Since how many years is LA's family staying at this address",
                ),
                F("vicinity_occupation", "Occupation as per vicinity"),
                F("vicinity_company", "Name of company as per vicinity"),
                F("vicinity_income", "Income as per vicinity"),
                F("vicinity_family_income", "Family income as per vicinity"),
                TABLE(
                    "neighbours",
                    "Persons met during the vicinity check",
                    NEIGHBOUR_COLUMNS,
                    doc="neighbours",
                ),
                NARRATIVE("vicinity_remarks", "Remarks / details", doc="vicinity_remarks"),
                F(
                    "vicinity_conclusion",
                    "Vicinity check conclusion",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                ),
                TABLE(
                    "hospitals",
                    "Hospital / doctor / chemist checks",
                    HOSPITAL_COLUMNS,
                    doc="hospitals",
                ),
                F("medical_conclusion", "Medical check conclusion", col_span=12),
            ],
        ),
        S(
            "dbrcd",
            "In case of DBRCD — death certificate / cemetery verification",
            [
                F("authority_name", "Name of authority"),
                F("authority_designation", "Designation and location"),
                F("authority_contact", "Contact number", type=FieldType.PHONE),
                F("death_register_date", "Date of death in register", type=FieldType.DATE),
                F("dc_issue_date", "Death certificate issue date", type=FieldType.DATE),
                F("dbrcd_cause_of_death", "Cause of death (if available)", doc="cause_of_death"),
                F("cremation_details", "Life Assured cremation / burial and timing"),
                F(
                    "dc_verified",
                    "Death certificate verified",
                    type=FieldType.SELECT,
                    options=["Genuine", "Bogus", "Not applicable"],
                ),
            ],
        ),
        S(
            "other_insurance",
            "Other insurance details",
            [
                TABLE(
                    "other_policies", "Other policies", OTHER_POLICY_COLUMNS, doc="other_policies"
                ),
            ],
            description=(
                "Collect the husband's insurance details if the Life Assured is a "
                "housewife, and the parents' details if the Life Assured is a student."
            ),
        ),
        S(
            "family_history",
            "Family History",
            [TABLE("family_members", "Family members", FAMILY_COLUMNS, doc="family_members")],
        ),
        S(
            "overall",
            "Overall Remarks / Conclusion",
            [
                NARRATIVE("discreet_check", "Discreet check", doc="vicinity_remarks"),
                NARRATIVE("overall_remarks", "Overall remarks", doc="overall_remarks"),
            ],
        ),
        photographs_section(
            ["First visit photographs (geo tagged)", "Second visit photographs (geo tagged)"]
        ),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.9 ICICI Prudential — Payout Verification Form
# --------------------------------------------------------------------------- #
ICICI_PAYOUT = T(
    code="ICICI_PAYOUT",
    name="ICICI Prudential — Payout Verification Form",
    company="ICICI",
    case_type="PAYOUT_VERIFICATION",
    source_document="investigation_docs/Icici Payout.docx",
    description="Fields marked * are mandatory on the client's form.",
    sections=[
        S(
            "case_header",
            "Payout verification",
            [
                BANK("policy_number", "Policy Number *", "policy_number"),
                BANK("krn_no", "KRN", "krn_no"),
                BANK(
                    "customer_name", "Customer Name *", "life_assured_name", doc="life_assured_name"
                ),
                F("assignment_request_given", "Assignment Request Given *", required=True),
                BANK(
                    "allocation_date",
                    "Allocation Date *",
                    "received_at",
                    type=FieldType.DATE,
                    doc="allocation_date",
                ),
                F("father_name", "Father Name *", required=True),
                F(
                    "field_visit_datetime",
                    "Date and time of field visit *",
                    type=FieldType.DATETIME,
                    required=True,
                    doc="date_of_visit",
                ),
                F(
                    "nominee_name",
                    "Nominee Name *",
                    required=True,
                    prefill="nominee_name",
                    doc="nominee_name",
                ),
                F("nominee_dob", "Nominee DOB *", type=FieldType.DATE, doc="nominee_dob"),
                F(
                    "appointment_call_datetime",
                    "Date and time of appointment call",
                    type=FieldType.DATETIME,
                ),
            ],
        ),
        S(
            "existing_address",
            "Existing Address Details *",
            [
                F(
                    "existing_traceability",
                    "Traceable",
                    type=FieldType.SELECT,
                    options=["Traceable", "Not traceable"],
                    required=True,
                ),
                BANK(
                    "existing_address",
                    "Address",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                BANK("existing_pin_code", "Pin Code", "pin_code"),
                F("existing_landmark", "Landmark"),
                F("existing_landline", "Landline No & Extension Number"),
                F("existing_email1", "E-mail ID 1", type=FieldType.EMAIL),
                F("existing_email2", "E-mail ID 2", type=FieldType.EMAIL),
                BANK(
                    "existing_mobile",
                    "Mobile Number *",
                    "contact_number",
                    type=FieldType.PHONE,
                    doc="contact_number",
                ),
            ],
        ),
        S(
            "new_address",
            "New Address (if any) *",
            [
                F("new_address", "Address", type=FieldType.TEXTAREA, col_span=12),
                F("new_pin_code", "Pin Code"),
                F("new_landmark", "Landmark"),
                F("new_landline", "Landline No & Extension Number"),
                F("new_email1", "E-mail ID 1", type=FieldType.EMAIL),
                F("new_email2", "E-mail ID 2", type=FieldType.EMAIL),
                F("new_phone", "Phone Number 1", type=FieldType.PHONE),
            ],
        ),
        S(
            "third_party",
            "Third-party confirmation",
            [
                F("representative_name", "Customer representative name (if any)"),
                F("representative_relationship", "Relationship with the customer"),
                F(
                    "representative_contact",
                    "Contact number of the representative *",
                    type=FieldType.PHONE,
                ),
                NARRATIVE("representative_comments", "Representative comments"),
            ],
            description=(
                "Complete when the subscriber is not available — spouse, children, "
                "relative or neighbour."
            ),
        ),
        S(
            "vicinity",
            "Details obtained during vicinity check *",
            [
                F("vicinity_person_name", "Name of the person met"),
                F(
                    "vicinity_person_address",
                    "Address of the person met",
                    type=FieldType.TEXTAREA,
                    col_span=12,
                ),
                F(
                    "vicinity_person_contact",
                    "Contact number of the person met *",
                    type=FieldType.PHONE,
                ),
                TABLE("neighbours", "Vicinity persons met", NEIGHBOUR_COLUMNS, doc="neighbours"),
            ],
        ),
        S(
            "residence_status",
            "Residence Status",
            [
                F("house_type", "Type of House", type=FieldType.SELECT, options=HOUSE_TYPE),
                F(
                    "traceability",
                    "Traceability",
                    type=FieldType.SELECT,
                    options=["Traceable", "Not traceable"],
                ),
                F("location", "Location", type=FieldType.SELECT, options=LOCALITY),
                F("ownership", "Ownership *", type=FieldType.SELECT, options=OWNERSHIP),
            ],
        ),
        S(
            "contactability",
            "Contactability",
            [
                F(
                    "contacted_at_address",
                    "Customer contacted at address",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    required=True,
                ),
                F(
                    "contacted_over_phone",
                    "Customer contacted over phone",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    required=True,
                ),
            ],
        ),
        S(
            "final",
            "Final remarks and declaration",
            [
                NARRATIVE("overall_remarks", "Final Remarks", doc="overall_remarks"),
                F("final_status", "Final Status", col_span=12, doc="conclusion"),
                F(
                    "declaration_accepted",
                    "I confirm the report and findings are true to the best of the "
                    "investigator's knowledge and assessment",
                    type=FieldType.BOOLEAN,
                    required=True,
                    col_span=12,
                ),
            ],
        ),
        photographs_section(["Customer / representative photograph *", "ID proofs *"]),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.10 ICICI Prudential — Customer Verification Form (New Business / LMS)
# --------------------------------------------------------------------------- #
ICICI_LMS = T(
    code="ICICI_NEW_BUSINESS",
    name="ICICI Prudential — Customer Verification Form (New Business)",
    company="ICICI",
    case_type="NEW_BUSINESS_VERIFICATION",
    source_document="investigation_docs/LMS.docx",
    sections=[
        S(
            "header",
            "Customer Verification Form — New Business",
            [
                BANK("application_number", "Application Number", "application_number"),
                BANK(
                    "life_assured_name",
                    "Customer Name",
                    "life_assured_name",
                    doc="life_assured_name",
                ),
                F(
                    "vendor_name",
                    "Vendor Name",
                    doc="agency_name",
                    default="Virtual Investigation Services",
                ),
                BANK("krn_no", "KRN", "krn_no"),
                F(
                    "date_of_visit",
                    "Date of Visit",
                    type=FieldType.DATE,
                    required=True,
                    doc="date_of_visit",
                ),
                F("time_of_visit", "Time of Visit", type=FieldType.TIME, doc="time_of_visit"),
            ],
        ),
        S(
            "checklist",
            "Verification checklist",
            [
                F(
                    "contactability",
                    "Contactability",
                    type=FieldType.SELECT,
                    options=["Contactable", "Not contactable"],
                ),
                F("address_traced", "Address Traced", type=FieldType.SELECT, options=YES_NO),
                F(
                    "la_existence_verified",
                    "LA Existence Verified",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F("duration_of_stay", "Duration of Stay"),
                F(
                    "applied_for_policy",
                    "Applied for Policy",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "occupation",
                    "Occupation",
                    type=FieldType.SELECT,
                    options=OCCUPATION_TYPE,
                    doc="la_occupation",
                ),
                F(
                    "met_policy_holder",
                    "Met Policy Holder",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    doc="person_met",
                ),
                F("designation", "Designation"),
                F("house_type", "Type of House", type=FieldType.SELECT, options=HOUSE_TYPE),
                F("company_name", "Company Name"),
                F("location", "Location", type=FieldType.SELECT, options=LOCALITY),
                F("annual_income", "Annual Income", doc="la_annual_income"),
                F("ownership", "Ownership", type=FieldType.SELECT, options=OWNERSHIP),
                F("behavioural_issue", "Behavioural issue"),
                F("address_verified", "Address Verified", type=FieldType.SELECT, options=YES_NO),
                F("education", "Education", doc="la_qualification"),
                F("pan_no", "PAN no"),
                F(
                    "aadhar_no",
                    "Aadhar No",
                    help="Record only the masked number that appears on the document.",
                ),
                F("physical_observation", "Physical Observation"),
                F(
                    "marital_status",
                    "Marital Status",
                    type=FieldType.SELECT,
                    options=MARITAL_STATUS,
                    doc="la_marital_status",
                ),
            ],
        ),
        S(
            "vicinity",
            "Details obtained during vicinity check",
            [
                F("vicinity_person_name", "Name of the person met"),
                F(
                    "vicinity_person_address",
                    "Address of the person met",
                    type=FieldType.TEXTAREA,
                    col_span=12,
                ),
                F("vicinity_person_contact", "Contact no", type=FieldType.PHONE),
                NARRATIVE("vicinity_remarks", "Vicinity check remarks", doc="vicinity_remarks"),
            ],
        ),
        S(
            "post_office",
            "Post Office details (when the address is not traceable)",
            [
                F("postal_official_name", "Postal official's name"),
                F("postal_official_contact", "Contact number of official", type=FieldType.PHONE),
                F("post_office_name", "Post Office name"),
                F("post_office_photo", "Post office photo", type=FieldType.SELECT, options=YES_NO),
            ],
        ),
        S(
            "final_remarks",
            "Final Remarks",
            [
                NARRATIVE("discreet_check", "Discreet Check"),
                NARRATIVE("overall_remarks", "Overall Remarks", doc="overall_remarks"),
                TABLE(
                    "documents_collected",
                    "Supporting documents",
                    DOCUMENT_COLUMNS,
                    doc="documents_collected",
                ),
            ],
        ),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.11 Kotak Life — Detailed Investigation [Pre-Claims] Report
# --------------------------------------------------------------------------- #
KOTAK_PRE_CLAIM = T(
    code="KOTAK_PRE_CLAIM",
    name="Kotak Life — Detailed Investigation [Pre-Claims] Report",
    company="KOTAK",
    case_type="PRE_CLAIM",
    source_document="investigation_docs/Kotak Life.docx",
    sections=[
        agency_section(),
        S(
            "decision",
            "Decision",
            [
                F(
                    "decision",
                    "Decision (Positive / Negative)",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                    required=True,
                    doc="outcome",
                ),
                F("decision_specify", "Please specify", col_span=12, doc="outcome_reason"),
            ],
        ),
        S(
            "proposal_policy",
            "Proposal / Policy details",
            [
                BANK("application_number", "App No", "application_number"),
                BANK("policy_number", "Policy No", "policy_number"),
                F("policy_issued_date", "Policy Issued Date", type=FieldType.DATE),
                BANK("sum_assured", "Sum Insured", "sum_assured", type=FieldType.CURRENCY),
                F("policy_duration", "Policy Duration"),
            ],
        ),
        S(
            "proposal_verification",
            "Proposal verification",
            [
                TABLE(
                    "proposal_matrix",
                    "Personal details of the insured — proposal vs profile check",
                    PROPOSAL_MATCH_COLUMNS,
                ),
                NARRATIVE(
                    "discrepancy_details",
                    "Please specify in detail any considerable difference or "
                    "discrepancy in the above details",
                ),
            ],
            description=(
                "Compare each detail as stated in the proposal form against what the "
                "profile check established: name, DOB/age, income, occupation, "
                "workplace address, health and hospitalisation, marital status, "
                "qualification, address, nominee, PEP and hazardous hobbies."
            ),
        ),
        S(
            "family_history",
            "Family History",
            [TABLE("family_members", "Family members", FAMILY_COLUMNS, doc="family_members")],
        ),
        S(
            "other_policies_section",
            "Other policy details & family insurance details",
            [
                TABLE(
                    "other_policies",
                    "Life / mediclaim / critical illness policies",
                    OTHER_POLICY_COLUMNS,
                    doc="other_policies",
                )
            ],
        ),
        S(
            "vicinity_check",
            "Vicinity Check",
            [
                TABLE("neighbours", "Persons met", NEIGHBOUR_COLUMNS, doc="neighbours"),
                NARRATIVE(
                    "vicinity_remarks", "Findings / observations / remarks", doc="vicinity_remarks"
                ),
            ],
        ),
        S(
            "workplace_check",
            "Workplace Check",
            [
                F("employer_name", "(A) In case of salaried — name of employer"),
                NARRATIVE(
                    "employee_details",
                    "LA designation and income, general health / habit, behaviour",
                ),
                F(
                    "salary_documents",
                    "Salary slip / Income Tax Return / Form 16",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE(
                    "sick_leave_details",
                    "Sick leave details, reason for availing sick leave, medical "
                    "documents, employer certificate",
                ),
                F(
                    "business_name",
                    "(B) In case of business / self-employed / shop / vendor — name",
                ),
                NARRATIVE(
                    "business_findings",
                    "Findings / observations / remarks (mismatch in age, "
                    "occupation, income, health, habit)",
                ),
                F(
                    "shop_photo",
                    "Photo of shop / business",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
            ],
        ),
        S(
            "online_checks",
            "Newspaper / Internet check",
            [
                F("visit_verification", "By visit / verification"),
                NARRATIVE(
                    "online_checks",
                    "By online checks — LinkedIn, business registration proof, website "
                    "checks, ration card and voter ID search for suspected age difference",
                ),
                F(
                    "snapshot_attached",
                    "Snapshot taken and attached with the report",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
            ],
        ),
        S(
            "agency_findings",
            "Investigation Agency Overall Findings",
            [
                NARRATIVE("overall_remarks", "Overall remarks", doc="overall_remarks"),
                NARRATIVE("other_information", "Other information not covered in the report above"),
            ],
        ),
        S(
            "documents_procured",
            "Documents Procured / Collected",
            [
                TABLE(
                    "documents_collected",
                    "Documents collected",
                    DOCUMENT_COLUMNS,
                    doc="documents_collected",
                )
            ],
        ),
        photographs_section(["First visit photographs", "Second visit photographs"]),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.12 Kotak Life — Discreet Check
#
# The source document is "Kotak Discreate Cheak.docx"; it was previously filed
# under ICICI, which put a Kotak form on the wrong client's menu.
# --------------------------------------------------------------------------- #
ICICI_DISCREET = T(
    code="KOTAK_DISCREET_CHECK",
    name="Kotak Life — Discreet Check Report",
    company="KOTAK",
    case_type="DISCREET_CHECK",
    source_document="investigation_docs/Kotak Discreate Cheak.docx",
    sections=[
        S(
            "brief_details",
            "Brief Details (as per company)",
            [
                F("type_of_check", "Type of check", default="Discreet Check", col_span=6),
                BANK("krn_no", "KRN", "krn_no"),
                F(
                    "report_submission_date",
                    "Report Submission Date",
                    type=FieldType.DATE,
                    required=True,
                    doc="report_submission_date",
                ),
            ],
        ),
        S(
            "la_details",
            "Life Assured details",
            [
                BANK("life_assured_name", "Name (as per proposal)", "life_assured_name"),
                F("name_if_different", "If different from proposal"),
                F("dob_age_proposal", "DOB / age (as per proposal)", doc="la_dob"),
                F("dob_age_if_different", "If different from proposal"),
                BANK(
                    "address_proposal",
                    "Address (as per proposal)",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                F(
                    "address_if_different",
                    "If different from proposal",
                    type=FieldType.TEXTAREA,
                    col_span=12,
                ),
                F("education_proposal", "Education (as per proposal)", doc="la_qualification"),
                F("education_if_different", "If different from proposal"),
            ],
        ),
        S(
            "detailed_report",
            "Complete Investigation Report — Discreet Check",
            [
                NARRATIVE(
                    "field_investigation_summary",
                    "Field Investigation Summary",
                    doc="vicinity_remarks",
                ),
                NARRATIVE("financial_status", "Financial Status"),
                NARRATIVE("residential_check", "Residential Check"),
                NARRATIVE("health_conditions", "Health Conditions"),
                NARRATIVE("conclusion_narrative", "Conclusion", doc="overall_remarks"),
            ],
        ),
        S(
            "enclosures",
            "Enclosures",
            [
                F(
                    "enclosures",
                    "Enclosures (live snaps, neighbours' videos, supporting)",
                    type=FieldType.TEXTAREA,
                    col_span=12,
                ),
                F(
                    "other_relevant_details",
                    "Any relevant details not mentioned above",
                    type=FieldType.TEXTAREA,
                    col_span=12,
                ),
            ],
            description=(
                "Documents and evidence procured during the investigation must be "
                "clear and readable."
            ),
        ),
        photographs_section(["Locality photographs", "House photographs"]),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.13 PNB MetLife — Scenario based verification
# --------------------------------------------------------------------------- #
PNB_PRE_CLAIM = T(
    code="PNBMET_PRE_CLAIM",
    name="PNB MetLife — Scenario-Based Verification Report",
    company="PNBMET",
    case_type="PRE_CLAIM",
    source_document="investigation_docs/PNB METLIFE.docx",
    sections=[
        S(
            "header",
            "Assignment details",
            [
                BANK("application_number", "Application No", "application_number"),
                F("agency_details", "Investigating agency details", doc="agency_name"),
                F("fe_name", "FE name", prefill="assigned_to_name", doc="field_investigator_name"),
                BANK(
                    "case_receipt_date",
                    "Date of case receipt",
                    "received_at",
                    type=FieldType.DATE,
                    doc="assignment_date",
                ),
                F(
                    "date_of_visit",
                    "Date of Visit",
                    type=FieldType.DATE,
                    required=True,
                    doc="date_of_visit",
                ),
                F(
                    "date_of_report",
                    "Date of Report",
                    type=FieldType.DATE,
                    doc="report_submission_date",
                ),
                F("overall_status", "Overall status", col_span=12, doc="conclusion"),
                BANK("life_assured_name", "LA Name", "life_assured_name"),
                BANK(
                    "la_address",
                    "Address",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                BANK("contact_number", "Mobile", "contact_number", type=FieldType.PHONE),
                F(
                    "status",
                    "Status",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                    required=True,
                    doc="outcome",
                ),
            ],
        ),
        S(
            "scenario",
            "Applicable scenario",
            [
                F(
                    "scenario",
                    "Which scenario applies?",
                    type=FieldType.RADIO,
                    required=True,
                    col_span=12,
                    options=[
                        "Scenario 1 — Life Assured met, alive and in good health",
                        "Scenario 2 — Life Assured alive and unhealthy",
                        "Scenario 3 — Life Assured deceased",
                        "Scenario 4 — LA not met at first attempt (house locked etc.)",
                        "Scenario 5 — Existence refused / identity not established / "
                        "address not traced",
                    ],
                ),
            ],
        ),
        S(
            "scenario_1",
            "Section 1 — If LA is alive and in good health",
            [
                F(
                    "s1_financial_status",
                    "1.1 Financial status of Life Assured",
                    type=FieldType.SELECT,
                    options=STANDARD_OF_LIVING,
                    doc="standard_of_living",
                ),
                F("s1_physical_appearance", "1.2 Life Assured's physical appearance checked"),
                F(
                    "s1_neighbour_check",
                    "1.3 Neighbour check done",
                    type=FieldType.SELECT,
                    options=["Checked", "Not checked"],
                ),
                F(
                    "s1_photographs",
                    "1.4 Photographs collected of LA / house",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE("s1_special_remarks", "Special remarks"),
            ],
        ),
        S(
            "scenario_2",
            "Section 2 — If LA is alive and unhealthy",
            [
                NARRATIVE(
                    "s2_disease_details",
                    "2.1 Details about the disease / illness (specify duration)",
                ),
                F(
                    "s2_financial_status",
                    "2.2 Financial status of Life Assured",
                    type=FieldType.SELECT,
                    options=STANDARD_OF_LIVING,
                ),
                NARRATIVE(
                    "s2_physical_appearance",
                    "2.3 Physical appearance checked — any abnormality observed",
                ),
                NARRATIVE("s2_vicinity_check", "2.4 Vicinity / neighbour check feedback"),
                F(
                    "s2_photographs",
                    "2.5 Photographs collected of LA / house",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
            ],
        ),
        S(
            "scenario_3",
            "Section 3 — If LA is deceased",
            [
                NARRATIVE(
                    "s3_disease_details",
                    "3.1 Details about the disease / illness, if any (duration)",
                ),
                F(
                    "s3_financial_status",
                    "3.2 Financial status of Life Assured",
                    type=FieldType.SELECT,
                    options=STANDARD_OF_LIVING,
                ),
                NARRATIVE(
                    "s3_physical_appearance", "3.3 Physical appearance — any abnormality observed"
                ),
                NARRATIVE("s3_vicinity_check", "3.4 Vicinity / neighbour check"),
                F(
                    "s3_photographs",
                    "3.5 Photographs collected of house / nearby landmark",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "s3_date_of_death",
                    "3.6 Date of death",
                    type=FieldType.DATE,
                    doc="date_of_death",
                ),
                F("s3_place_of_death", "3.6 Place of death", doc="place_of_death"),
            ],
        ),
        S(
            "procedural",
            "Scenarios 4 and 5 — procedure followed",
            [
                F(
                    "second_attempt_made",
                    "One more attempt made",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                NARRATIVE(
                    "family_relative_check",
                    "Family / relative and neighbourhood / vicinity check as listed",
                ),
                NARRATIVE(
                    "workplace_enquiry",
                    "Workplace enquiry — existence, age, occupation, income, "
                    "health, habits, physical appearance",
                ),
            ],
        ),
        S(
            "findings",
            "Findings",
            [
                NARRATIVE("vicinity_remarks", "Vicinity Check", doc="vicinity_remarks"),
                NARRATIVE("overall_remarks", "Overall Remark", doc="overall_remarks"),
                TABLE("neighbours", "Persons met", NEIGHBOUR_COLUMNS, doc="neighbours"),
            ],
        ),
        outcome_section(),
    ],
)


INVESTIGATION_TEMPLATES: tuple[T, ...] = (
    ADITYA_BIRLA_PRE_ISSUANCE,
    BAJAJ_PRE_ISSUANCE,
    BAXA_PRE_CLAIM,
    BANDHAN_PRE_ISSUANCE,
    HDFC_PROFILE_CHECK,
    HSBC_PRE_ISSUANCE,
    HSBC_MEDICAL_SEEDING,
    ICICI_PROFILE_CHECK,
    ICICI_PAYOUT,
    ICICI_LMS,
    KOTAK_PRE_CLAIM,
    ICICI_DISCREET,
    PNB_PRE_CLAIM,
)
