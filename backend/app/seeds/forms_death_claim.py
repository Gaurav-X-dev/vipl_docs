"""Seeded death-claim form layouts, transcribed from the supplied .docx files.

See ``docs/ATTACHMENT_ANALYSIS.md`` §6.14 – §6.18.
"""

from __future__ import annotations

from app.models.enums import FieldType
from app.seeds.form_dsl import (
    BANK,
    DOCUMENT_COLUMNS,
    EVIDENCE_STATUS,
    FAMILY_COLUMNS,
    HEALTH_STATUS,
    HOSPITAL_COLUMNS,
    INTERIM_FINAL,
    KEY_SENSING,
    MARITAL_STATUS,
    NARRATIVE,
    NEIGHBOUR_COLUMNS,
    OCCUPATION_TYPE,
    OTHER_POLICY_COLUMNS,
    POSITIVE_NEGATIVE,
    STANDARD_OF_LIVING,
    TABLE,
    YES_NO,
    YES_NO_NA,
    F,
    S,
    T,
    outcome_section,
    photographs_section,
)

KEY_SENSING_ITEMS: tuple[tuple[str, str], ...] = (
    ("profile_mismatch", "Profile Mismatch"),
    ("medical_non_disclosure", "Medical non-disclosure"),
    ("death_before_issuance", "Death before issuance (DBRCD)"),
    ("impersonation", "Impersonation"),
    ("forged_documents", "Forged / tampering of documents"),
    ("nexus_involvement", "Nexus involvement"),
    ("industry_shopping", "Industry shopping"),
    ("other_adverse_findings", "Any other adverse findings"),
    ("no_adverse_findings", "No adverse findings"),
)


def _key_sensing_section() -> S:
    fields: list[F] = []
    for key, label in KEY_SENSING_ITEMS:
        fields.extend(
            [
                F(key, label, type=FieldType.SELECT, options=KEY_SENSING, col_span=4, doc=key),
                F(f"{key}_source", f"{label} — details of mismatch and source", col_span=4),
                F(f"{key}_evidence", f"{label} — evidence details / remarks", col_span=4),
            ]
        )
    return S("key_sensing", "Key sensing of the case", fields)


def _claim_details_section() -> S:
    return S(
        "claim_details",
        "Claim details (for the investigator's reference)",
        [
            BANK("policy_number", "Policy No.", "policy_number"),
            F(
                "type_of_claim",
                "Type of Claim",
                type=FieldType.SELECT,
                default="Death Claim",
                options=["Death Claim", "Critical Illness", "Hospital Rider Claim"],
            ),
            BANK("life_assured_name", "Name of LA", "life_assured_name"),
            F("la_dob_age", "Date of Birth / Age of L.A.", doc="la_dob"),
            F(
                "la_occupation",
                "Occupation of L.A.",
                type=FieldType.SELECT,
                options=OCCUPATION_TYPE,
                doc="la_occupation",
            ),
            F("la_income", "Income of L.A.", doc="la_annual_income"),
            BANK("la_city_state", "State / City of LA", "city", doc="city"),
            BANK(
                "rcd", "Risk comm. date", "risk_commencement_date", type=FieldType.DATE, doc="rcd"
            ),
            F(
                "date_of_death",
                "Date of Death",
                type=FieldType.DATE,
                required=True,
                doc="date_of_death",
            ),
            BANK("sum_assured", "Sum Assured", "sum_assured", type=FieldType.CURRENCY),
            F("cause_of_death", "Cause of Death", required=True, doc="cause_of_death"),
            F("place_of_death", "Place of Death", doc="place_of_death"),
            F("claimant_name", "Name of Claimant", required=True, doc="claimant_name"),
            F("claimant_age", "Age of Claimant", doc="claimant_age"),
            F("claimant_relation", "Relation with L.A.", doc="claimant_relation"),
            F("claimant_occupation", "Occupation of Claimant"),
            F("claimant_income", "Income of Claimant"),
            F(
                "claimant_address",
                "State / City of Claimant",
                type=FieldType.TEXTAREA,
                col_span=12,
                doc="claimant_address",
            ),
            BANK(
                "contact_number",
                "Contact no / Mobile or Phone",
                "contact_number",
                type=FieldType.PHONE,
            ),
            BANK(
                "case_assignment_date",
                "Case assignment date",
                "received_at",
                type=FieldType.DATE,
                doc="assignment_date",
            ),
            F("first_report_date", "1st report submission date", type=FieldType.DATE),
            F(
                "final_report_date",
                "Final report submission date",
                type=FieldType.DATE,
                doc="report_submission_date",
            ),
            F(
                "negative_evidence_type",
                "Type of negative evidence collected",
                type=FieldType.SELECT,
                options=["Primary", "Secondary", "Both", "Not applicable"],
            ),
            F("negative_evidence_source", "Source of negative evidence collected"),
            F(
                "rti_applied",
                "Any RTI applied",
                type=FieldType.SELECT,
                options=YES_NO_NA,
                doc="rti_applied",
            ),
            F("rti_status", "RTI status", doc="rti_status"),
        ],
    )


def _la_profile_section() -> S:
    return S(
        "la_profile",
        "Life Assured's profile",
        [
            BANK("profile_name", "Name", "life_assured_name", doc="life_assured_name"),
            F("profile_dob", "DOB", type=FieldType.DATE, doc="la_dob"),
            F("profile_age", "Age", doc="la_age"),
            F("profile_dod", "DOD", type=FieldType.DATE, doc="date_of_death"),
            F(
                "profile_marital_status",
                "Marital Status",
                type=FieldType.SELECT,
                options=MARITAL_STATUS,
                doc="la_marital_status",
            ),
            F("profile_occupation", "Occupation", doc="la_occupation"),
            F("profile_annual_income", "Annual Income", doc="la_annual_income"),
            F("profile_qualification", "Qualification", doc="la_qualification"),
            BANK(
                "profile_address",
                "Address",
                "address",
                type=FieldType.TEXTAREA,
                doc="la_address",
                col_span=12,
            ),
            F(
                "beneficiary_relationship",
                "Claimant / beneficiary relationship",
                doc="claimant_relation",
            ),
            NARRATIVE("discrepancy_noted", "Discrepancy / mismatch noted, if any"),
        ],
    )


def _residence_check_section() -> S:
    return S(
        "residence_check",
        "LA residence check",
        [
            F(
                "standard_of_living",
                "Standard of living (APL / BPL / high income group)",
                type=FieldType.SELECT,
                options=STANDARD_OF_LIVING,
                doc="standard_of_living",
            ),
            F(
                "kyc_and_contact",
                "KYC & contact number",
                type=FieldType.SELECT,
                options=EVIDENCE_STATUS,
            ),
            NARRATIVE("medical_records", "Past & present medical records, consultation notes"),
            F("income_confirmation", "Annual income confirmation"),
            NARRATIVE("purpose_for_insurance", "Purpose for insurance"),
            NARRATIVE("other_insurance_details", "Other insurance details"),
        ],
    )


# --------------------------------------------------------------------------- #
# 6.14 Bajaj Allianz and HDFC Life share this death claim format
# --------------------------------------------------------------------------- #
def _standard_death_claim_sections() -> list[S]:
    return [
        S(
            "report_status_section",
            "Report status",
            [
                F(
                    "report_status",
                    "Report status (Interim / Final)",
                    type=FieldType.SELECT,
                    options=INTERIM_FINAL,
                    required=True,
                    doc="report_status",
                ),
                F(
                    "investigation_outcome",
                    "Investigation outcome",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                    required=True,
                    doc="outcome",
                ),
                NARRATIVE("case_details", "Case details"),
                NARRATIVE("suspicious_points", "Suspicious points"),
            ],
        ),
        _claim_details_section(),
        _la_profile_section(),
        S(
            "family_details",
            "Family details & history",
            [
                TABLE("family_members", "Family members", FAMILY_COLUMNS, doc="family_members"),
                NARRATIVE("nominee_details", "Nominee details and statement"),
                F(
                    "age_proofs_collected",
                    "Ration card / Voter ID or other age proofs collected for all family members",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                    col_span=12,
                ),
            ],
        ),
        _residence_check_section(),
        S(
            "neighbourhood_check",
            "Neighbourhood check",
            [
                TABLE(
                    "neighbours", "Persons met (5-6 people)", NEIGHBOUR_COLUMNS, doc="neighbours"
                ),
                NARRATIVE(
                    "neighbourhood_summary",
                    "Summary of the details shared by the above individuals",
                ),
            ],
            description=(
                "Check the LA's age, habits, occupation, illness and hospitalisation "
                "details, and obtain a written statement with name and contact number."
            ),
        ),
        S(
            "medical_checks",
            "Doctor, hospital, pathology and chemist checks",
            [
                NARRATIVE(
                    "family_doctor",
                    "Family doctor — period known to the LA, habits, illness and "
                    "duration, contact number (certificate to be collected)",
                ),
                NARRATIVE(
                    "last_treating_doctor",
                    "Last treating doctor — condition at admission, diagnosis and "
                    "treatment given, contact number",
                ),
                TABLE(
                    "hospitals",
                    "Hospitals / labs / chemists visited",
                    HOSPITAL_COLUMNS,
                    doc="hospitals",
                ),
                NARRATIVE(
                    "hospital_summary", "Summary of information received from the hospital checks"
                ),
            ],
        ),
        S(
            "workplace_check",
            "Occupation / workplace check",
            [
                F("employer_name", "In case of salaried — name of employer"),
                NARRATIVE(
                    "employee_profile",
                    "LA designation and income, general health / habit, behaviour",
                ),
                F("contact_person", "Name & address of the contact person / manager"),
                F(
                    "employer_certificate",
                    "Duly filled employer certificate collected",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "salary_documents",
                    "Salary slip / ITR / Form 16",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE(
                    "leave_records",
                    "Leave records, reason for sick leaves, and the medical "
                    "documents submitted for them",
                ),
                F("business_name", "If self-employed — name of the business"),
                F("business_location", "Location of business"),
                F("business_type", "Type of business (proprietorship, partnership etc.)"),
                F("business_bank_account", "Business bank account details"),
                F(
                    "business_registration",
                    "Business registration document collected",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F("gst_details", "GST details"),
            ],
        ),
        S(
            "police_verification",
            "Police verification",
            [
                F(
                    "type_of_death",
                    "Type of death",
                    type=FieldType.SELECT,
                    options=[
                        "Natural",
                        "Accident",
                        "Suicide",
                        "Murder",
                        "Poisoning",
                        "Not established",
                    ],
                    doc="type_of_death",
                ),
                NARRATIVE(
                    "incident_circumstances",
                    "Circumstances of the incident and death in detail, with date and time",
                ),
                NARRATIVE("fir_summary", "Summary of FIR"),
                NARRATIVE("pmr_summary", "Summary of PMR"),
                F(
                    "viscera_report",
                    "Viscera report (if any)",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE("final_police_report", "Final police report"),
            ],
            description=("Mandatory for accidental, suicide, poisoning and murder cases."),
        ),
        S(
            "cremation_burial",
            "Cremation and burial",
            [
                F(
                    "death_register_copy",
                    "Copy of death register collected",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "cremation_slip",
                    "Cremation / burial slip collected",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE("cremation_findings", "Findings / remarks"),
            ],
        ),
        S(
            "document_verification",
            "Document verification",
            [
                NARRATIVE(
                    "age_proof_verification",
                    "Age proof verification, in case forgery or tampering is "
                    "suspected during investigation",
                ),
                F(
                    "death_certificate_verified",
                    "Death certificate verified with the issuing authority",
                    type=FieldType.SELECT,
                    options=["Genuine", "Bogus", "Pending"],
                ),
                NARRATIVE("death_certificate_remarks", "Remarks", doc="death_certificate_remarks"),
                NARRATIVE(
                    "newspaper_internet_check",
                    "Newspaper / internet check — cuttings collected and online "
                    "validation of the age proof",
                ),
            ],
        ),
        S(
            "panchayat_checks",
            "Panchayat / village touch points",
            [
                F("panchayat_secretary", "Panchayat Secretary"),
                F("gram_pradhan", "Gram Pradhan / Sarpanch"),
                F("bdo", "Block Development Officer (BDO)"),
                F("circle_officer", "Circle Officer (CO)"),
                F("anganwadi", "Anganwadi Sevika / ANM / ASHA worker"),
                F("phc_chc", "Primary / Community Health Centre (PHC / CHC)"),
                F(
                    "other_authority",
                    "Other — Police Patil / Mamledar / Village officer / Councillor",
                ),
                NARRATIVE(
                    "panchayat_findings",
                    "Detailed check of the LA's age, occupation, income, health, "
                    "habits, date of death and type of death",
                ),
            ],
            description=(
                "Complete when the investigation location falls under a Panchayat or village."
            ),
        ),
        S(
            "advisor_check",
            "Advisor check",
            [
                F("advisor_name", "Advisor name"),
                F("advisor_contact", "Advisor contact number", type=FieldType.PHONE),
                F("advisor_relationship", "Relationship with LA and sourcing details"),
                NARRATIVE(
                    "advisor_feedback",
                    "Feedback from the advisor on the LA and the intimated claim",
                ),
            ],
        ),
        S(
            "overall",
            "Agency overall remarks and conclusion",
            [
                NARRATIVE("vicinity_remarks", "Vicinity Check", doc="vicinity_remarks"),
                NARRATIVE("overall_remarks", "Additional remarks", doc="overall_remarks"),
                NARRATIVE("conclusion", "Conclusion", doc="conclusion"),
                NARRATIVE("major_suspicion", "Major suspicion, if any"),
            ],
            description=(
                "The overall remark should summarise the findings and the "
                "recommendation, not repeat the whole report."
            ),
        ),
        S(
            "documents_collected_section",
            "List of documents collected",
            [
                TABLE(
                    "documents_collected",
                    "Documents collected",
                    DOCUMENT_COLUMNS,
                    doc="documents_collected",
                ),
                TABLE(
                    "other_policies",
                    "Other insurance policies",
                    OTHER_POLICY_COLUMNS,
                    doc="other_policies",
                ),
            ],
        ),
        S(
            "reactionables",
            "Interim / final tracking and re-actionables",
            [
                F("final_report_on", "Final report on", type=FieldType.DATE),
                F("interim_report_on", "Interim report on", type=FieldType.DATE),
                NARRATIVE("pending_checks", "Pending checks in order"),
                NARRATIVE(
                    "actionable_1",
                    "Further actionable 01 — given (date and time) / update received",
                ),
                NARRATIVE(
                    "actionable_2",
                    "Further actionable 02 — given (date and time) / update received",
                ),
            ],
        ),
        photographs_section(
            [
                "Photographs of the LA with family / friends when alive",
                "Photographs of the LA's house, inside and outside",
                "Geo-tagged evidence photographs",
            ]
        ),
        outcome_section(),
    ]


BAJAJ_DEATH_CLAIM = T(
    code="BAJAJ_DEATH_CLAIM",
    name="Bajaj Allianz — Death Claim Investigation Report",
    company="BAJAJ",
    case_type="DEATH_CLAIM",
    source_document="death_claim_docs/Bajaj death claim.docx",
    sections=_standard_death_claim_sections(),
)

HDFC_DEATH_CLAIM = T(
    code="HDFC_DEATH_CLAIM",
    name="HDFC Life — Death Claim Investigation Report",
    company="HDFC",
    case_type="DEATH_CLAIM",
    source_document="death_claim_docs/HDFC Death Claim.docx",
    description=(
        "All statements and translations must be collected in the HDFC Life format; "
        "every procured document must be listed with an annexure name and number and "
        "attested with the agency seal."
    ),
    sections=_standard_death_claim_sections(),
)


# --------------------------------------------------------------------------- #
# 6.15 ICICI Prudential — Claim Investigation Report (complete)
# --------------------------------------------------------------------------- #
_ICICI_PART1_ROWS: tuple[tuple[str, str], ...] = (
    ("name", "Name"),
    ("address", "Address"),
    ("dob", "Date of Birth"),
    ("age", "Age"),
    ("marital_status", "Marital Status"),
    ("occupation", "Occupation"),
    ("annual_income", "Annual Income"),
    ("education", "Education"),
    ("other_insurance", "Other life / health insurance"),
    ("la_photograph", "Life assured's photograph"),
    ("la_kyc", "Life assured's KYC"),
    ("date_of_death", "Date of death"),
    ("place_of_death", "Place of death"),
    ("cause_of_death", "Cause of death"),
    ("nominee_name", "Nominee's name"),
    ("nominee_relationship", "Nominee's relationship"),
    ("other_mismatch", "Any other mismatch"),
)

_ICICI_PART1_FIELDS: list[F] = []
for _key, _label in _ICICI_PART1_ROWS:
    _ICICI_PART1_FIELDS.extend(
        [
            F(f"p1_{_key}", f"{_label} — as per investigation", col_span=4),
            F(
                f"p1_{_key}_mismatch",
                f"{_label} — mismatch noted",
                type=FieldType.SELECT,
                options=KEY_SENSING,
                col_span=3,
            ),
            F(f"p1_{_key}_source", f"{_label} — information source", col_span=3),
            F(
                f"p1_{_key}_evidence",
                f"{_label} — evidence procured",
                type=FieldType.SELECT,
                options=YES_NO,
                col_span=2,
            ),
        ]
    )

ICICI_DEATH_CLAIM = T(
    code="ICICI_DEATH_CLAIM",
    name="ICICI Prudential — Claim Investigation Report",
    company="ICICI",
    case_type="DEATH_CLAIM",
    source_document="death_claim_docs/ICICI Death Claim.docx",
    sections=[
        S(
            "claim_information",
            "Claim information",
            [
                F(
                    "type_of_investigation",
                    "Type of investigation",
                    type=FieldType.SELECT,
                    options=[
                        "Complete Investigation",
                        "Field Triggered Investigation",
                        "Desk Investigation",
                    ],
                    default="Complete Investigation",
                ),
                BANK("krn_no", "Key reference number", "krn_no"),
                BANK("contract_no", "Contract No", "policy_number", doc="policy_number"),
                BANK("life_assured_name", "Life Assured's name", "life_assured_name"),
                BANK("sum_assured", "Sum assured", "sum_assured", type=FieldType.CURRENCY),
                F(
                    "claimant_name",
                    "Proposer's / Claimant's name",
                    required=True,
                    doc="claimant_name",
                ),
                BANK(
                    "rcd",
                    "Risk commencement date",
                    "risk_commencement_date",
                    type=FieldType.DATE,
                    doc="rcd",
                ),
                BANK("product_name", "Product", "product_name"),
                F("agency_name", "Investigating Agency's name", doc="agency_name"),
                F(
                    "agency_contact",
                    "Investigating Agency's contact number",
                    type=FieldType.PHONE,
                    doc="agency_contact",
                ),
                F(
                    "field_investigator_name",
                    "Field investigator's name",
                    prefill="assigned_to_name",
                    doc="field_investigator_name",
                ),
                F(
                    "fi_contact_number",
                    "Field investigator's contact number",
                    type=FieldType.PHONE,
                    doc="fi_contact_number",
                ),
                BANK(
                    "allocation_date",
                    "Allocation date",
                    "received_at",
                    type=FieldType.DATE,
                    doc="allocation_date",
                ),
                F(
                    "report_submission_date",
                    "Date of report submission",
                    type=FieldType.DATE,
                    doc="report_submission_date",
                ),
            ],
        ),
        _key_sensing_section(),
        S(
            "part1",
            "Part 1 — Checks of details mentioned in the proposal / claim form",
            _ICICI_PART1_FIELDS,
        ),
        S(
            "family_details",
            "Family details",
            [
                TABLE("family_members", "Family members", FAMILY_COLUMNS, doc="family_members"),
                F(
                    "age_proof_parivar",
                    "Parivar Card collected",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                F(
                    "age_proof_voter",
                    "Voter ID card collected",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                F(
                    "age_proof_ration",
                    "Ration Card collected",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                F(
                    "age_proof_aadhaar",
                    "Aadhaar Card collected",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                F("age_proof_pan", "PAN card collected", type=FieldType.SELECT, options=YES_NO_NA),
                NARRATIVE("statement_details", "Statement details"),
                F(
                    "relationship_proof",
                    "Relationship proof",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F("kyc_documents", "KYC documents", type=FieldType.SELECT, options=EVIDENCE_STATUS),
            ],
        ),
        S(
            "residence_check",
            "LA residence check",
            [
                F(
                    "standard_of_living",
                    "Standard of living",
                    type=FieldType.SELECT,
                    options=STANDARD_OF_LIVING,
                    doc="standard_of_living",
                ),
                F(
                    "kyc_and_contact",
                    "KYC & contact number",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE("medical_records", "Past & present medical records, consultation notes"),
                F(
                    "income_supporting_documents",
                    "Annual income with supporting documents (bank statement / ITR / F-16)",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE("purpose_for_insurance", "Purpose for insurance"),
                NARRATIVE(
                    "other_insurance_details",
                    "Other insurance (including health insurance) details",
                ),
            ],
            description="Collect a photograph of the residence or premises.",
        ),
        S(
            "part2_detailed",
            "Part II — Detailed investigation report",
            [
                TABLE(
                    "neighbours",
                    "Discreet check at the LA's residence and workplace (5-6 people)",
                    NEIGHBOUR_COLUMNS,
                    doc="neighbours",
                ),
                NARRATIVE(
                    "discreet_summary",
                    "Summary of the details shared by the above individuals",
                    doc="vicinity_remarks",
                ),
                F(
                    "family_doctor_certificate",
                    "Family doctor certificate collected",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE("family_doctor_findings", "Family doctor — any other findings"),
                TABLE("hospitals", "Hospital checks", HOSPITAL_COLUMNS, doc="hospitals"),
                F(
                    "salaried_or_self_employed",
                    "Salaried or self-employed",
                    type=FieldType.SELECT,
                    options=["Salaried", "Self-employed", "Farming", "Not established"],
                ),
                F(
                    "employer_certificate",
                    "Duly filled employer certificate collected",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F("salary_slip", "Salary slip", type=FieldType.SELECT, options=EVIDENCE_STATUS),
                NARRATIVE("leave_records", "Leave records and reason for availing sick leaves"),
            ],
        ),
        S(
            "death_confirmation",
            "Death confirmation",
            [
                F(
                    "dc_verification_authority",
                    "Death certificate verification — checks at the issuing authority",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F("dc_mismatch", "Mismatch, if any", type=FieldType.SELECT, options=YES_NO_NA),
                NARRATIVE(
                    "dc_remarks",
                    "Remarks and RTI / evidence details",
                    doc="death_certificate_remarks",
                ),
                NARRATIVE(
                    "cremation_findings",
                    "Cremation documents verified / cremation related findings",
                ),
                F(
                    "local_authority_person",
                    "Anganwadi / ANM / Ward member / Sarpanch / Gram Sachiv / BLO / BDO — "
                    "details of the authority",
                    col_span=12,
                ),
                NARRATIVE("local_authority_remarks", "Local authority remarks"),
                NARRATIVE(
                    "last_treating_hospital",
                    "Last treating hospital where death occurred, with MCOD / "
                    "death summary (for natural death)",
                ),
            ],
        ),
        S(
            "unnatural_death",
            "Additional checks for unnatural death (suicide, murder, accident)",
            [
                F(
                    "type_of_death",
                    "Type of unnatural death",
                    type=FieldType.SELECT,
                    options=["Suicide", "Murder", "Accident", "Not applicable"],
                    doc="type_of_death",
                ),
                NARRATIVE("fir_gd_details", "FIR / GD details"),
                NARRATIVE("postmortem_details", "Postmortem details"),
                NARRATIVE("viscera_details", "Viscera / chemical analysis details"),
                NARRATIVE("final_police_report", "Final police report details"),
                NARRATIVE("court_order", "Court order or charge sheet details"),
                NARRATIVE("media_checks", "Media related checks (newspaper / social media)"),
            ],
        ),
        S(
            "nexus",
            "Negative location, fraud or nexus observations",
            [
                F("nexus_entity", "Nexus or details of the entity involved"),
                NARRATIVE("location_observations", "Location related observations"),
            ],
        ),
        S(
            "summary",
            "Summary of the investigation carried out",
            [
                NARRATIVE("vicinity_remarks", "Vicinity check", doc="vicinity_remarks"),
                NARRATIVE("nominee_statement", "Nominee statement"),
                NARRATIVE("overall_remarks", "Overall remark", doc="overall_remarks"),
                NARRATIVE(
                    "adverse_evidence",
                    "Details of evidence collected for adverse findings or profile mismatch",
                ),
            ],
        ),
        S(
            "checklist",
            "Checklist — important documents and photographs",
            [
                TABLE(
                    "documents_collected",
                    "Documents and photographs",
                    DOCUMENT_COLUMNS,
                    doc="documents_collected",
                )
            ],
        ),
        S(
            "rti_summary",
            "RTI summary",
            [
                TABLE(
                    "rti_items",
                    "RTI applications",
                    [
                        {"key": "reason", "label": "Reason for filing"},
                        {"key": "authority", "label": "Authority detail"},
                        {"key": "filed_date", "label": "Filed date"},
                        {"key": "reference", "label": "POD / reference number"},
                        {"key": "response_due", "label": "Tentative date of response"},
                    ],
                )
            ],
        ),
        S(
            "reassignments",
            "Findings on the re-actionables given",
            [
                F("reassign_1_reason", "First reassignment — reason"),
                NARRATIVE("reassign_1_response", "First reassignment — response"),
                F("reassign_2_reason", "Second reassignment — reason"),
                NARRATIVE("reassign_2_response", "Second reassignment — response"),
                F("reassign_3_reason", "Third reassignment — reason"),
                NARRATIVE("reassign_3_response", "Third reassignment — response"),
                F(
                    "declaration_accepted",
                    "Declaration — an affidavit is provided for all negative cases",
                    type=FieldType.BOOLEAN,
                    col_span=12,
                ),
            ],
        ),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.16 ICICI Prudential — FTI claim report
# --------------------------------------------------------------------------- #
_FTI_ROWS: tuple[tuple[str, str], ...] = (
    ("name", "Name"),
    ("age", "Age"),
    ("marital_status", "Marital Status"),
    ("occupation", "Occupation"),
    ("education", "Education"),
    ("other_insurance", "Other life / health insurance"),
)

_FTI_FIELDS: list[F] = []
for _key, _label in _FTI_ROWS:
    _FTI_FIELDS.extend(
        [
            F(f"fti_{_key}_nominee", f"{_label} — as per nominee / family members", col_span=6),
            F(f"fti_{_key}_vicinity", f"{_label} — as per vicinity", col_span=6),
        ]
    )

ICICI_FTI = T(
    code="ICICI_DEATH_CLAIM_FTI",
    name="ICICI Prudential — FTI Claim Investigation Report",
    company="ICICI",
    case_type="DEATH_CLAIM_FTI",
    source_document="death_claim_docs/FTI Icici.docx",
    sections=[
        S(
            "claim_information",
            "Claim information",
            [
                F(
                    "type_of_investigation",
                    "Type of investigation",
                    default="Field Triggered Investigation",
                ),
                BANK("krn_no", "Key reference number", "krn_no"),
                BANK("contract_no", "Contract No", "policy_number", doc="policy_number"),
                BANK("life_assured_name", "Life Assured's name", "life_assured_name"),
                BANK("sum_assured", "Sum assured", "sum_assured", type=FieldType.CURRENCY),
                F(
                    "claimant_name",
                    "Proposer's / Claimant's name",
                    required=True,
                    doc="claimant_name",
                ),
                BANK(
                    "rcd",
                    "Risk commencement date",
                    "risk_commencement_date",
                    type=FieldType.DATE,
                    doc="rcd",
                ),
                F("agency_name", "Investigating Agency's name", doc="agency_name"),
                F(
                    "agency_contact",
                    "Investigating Agency's contact number",
                    type=FieldType.PHONE,
                    doc="agency_contact",
                ),
                F(
                    "field_investigator_name",
                    "Field investigator's name",
                    prefill="assigned_to_name",
                    doc="field_investigator_name",
                ),
                F(
                    "fi_contact_number",
                    "Field investigator's contact number",
                    type=FieldType.PHONE,
                    doc="fi_contact_number",
                ),
                BANK(
                    "allocation_date",
                    "Allocation date",
                    "received_at",
                    type=FieldType.DATE,
                    doc="allocation_date",
                ),
                F(
                    "report_submission_date",
                    "Date of report submission",
                    type=FieldType.DATE,
                    doc="report_submission_date",
                ),
            ],
        ),
        S(
            "part1",
            "Part 1 — Check details of the life assured from nominee / family / vicinity",
            _FTI_FIELDS,
        ),
        S(
            "death_findings",
            "Death related findings for the life assured",
            [
                F(
                    "dod_nominee",
                    "Date of death — as per nominee / family",
                    type=FieldType.DATE,
                    required=True,
                    doc="date_of_death",
                ),
                F("dod_vicinity", "Date of death — as per vicinity", type=FieldType.DATE),
                F("pod_nominee", "Place of death — as per nominee / family", doc="place_of_death"),
                F("pod_vicinity", "Place of death — as per vicinity"),
                F("cod_nominee", "Cause of death — as per nominee / family", doc="cause_of_death"),
                F("cod_vicinity", "Cause of death — as per vicinity"),
                F(
                    "claim_form_mismatch",
                    "Any mismatch with the claim form found during the investigation",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                    col_span=12,
                ),
                F(
                    "evidence_type",
                    "Evidence: verbal or document",
                    type=FieldType.SELECT,
                    options=["Verbal", "Document", "Both", "None"],
                ),
            ],
        ),
        S(
            "family_details",
            "Family details (including nominee)",
            [
                TABLE("family_members", "Family members", FAMILY_COLUMNS, doc="family_members"),
                F(
                    "kyc_life_assured",
                    "KYC collected for the life assured",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "relationship_proof",
                    "Relationship proof collected for the nominee with the life assured",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "kyc_nominee",
                    "KYC collected for the nominee",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE(
                    "documents_not_collected_reason",
                    "If any of the above documents were not collected, mention the reason",
                ),
            ],
        ),
        S(
            "part2",
            "Part 2 — Detailed investigation report",
            [
                TABLE(
                    "neighbours",
                    "Family members and neighbours met",
                    NEIGHBOUR_COLUMNS,
                    doc="neighbours",
                ),
                NARRATIVE(
                    "neighbour_summary",
                    "Summary of the details shared by the above individuals",
                    doc="vicinity_remarks",
                ),
                F(
                    "dc_verification",
                    "Death certificate verification",
                    type=FieldType.SELECT,
                    options=["Verified", "Not verified", "Pending"],
                ),
                NARRATIVE(
                    "cremation_findings",
                    "Cremation / burial ground documents verified and related findings",
                ),
                F("met_person", "Met person and contact details", doc="person_met"),
                F(
                    "unnatural_death_type",
                    "Type of unnatural death (suicide / murder / accident)",
                    type=FieldType.SELECT,
                    options=["Suicide", "Murder", "Accident", "Not applicable"],
                    doc="type_of_death",
                ),
                NARRATIVE("unnatural_death_findings", "Details as per the investigation findings"),
            ],
        ),
        S(
            "checks_summary",
            "Summary and conclusion checklist",
            [
                NARRATIVE(
                    "check_date_cause",
                    "Exact date and cause of death — where, when and how the LA died",
                ),
                NARRATIVE(
                    "check_family_statements",
                    "Family members' statements and their contact numbers",
                ),
                NARRATIVE(
                    "check_neighbour_statements",
                    "Statements from neighbours and their contact numbers",
                ),
                NARRATIVE(
                    "check_occupation",
                    "Occupation verification — ITR / employer certificate / leave records",
                ),
                NARRATIVE("check_medical_history", "Past medical history of the life assured"),
                F(
                    "check_residence_pictures",
                    "Pictures of residence",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE(
                    "check_other_policies",
                    "History of other life and health policies held by the LA and family",
                ),
                F(
                    "check_pm_fir",
                    "PM and FIR copy",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                NARRATIVE("check_rti", "RTI to hospital or government institute"),
                F(
                    "check_suicide_ruled_out",
                    "Suicide ruled out",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                NARRATIVE("overall_remarks", "Remark", doc="overall_remarks"),
            ],
        ),
        _key_sensing_section(),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.17 SUD Life — Investigation Report
# --------------------------------------------------------------------------- #
SUD_DEATH_CLAIM = T(
    code="SUD_DEATH_CLAIM",
    name="SUD Life — Investigation Report",
    company="SUD",
    case_type="DEATH_CLAIM",
    source_document="death_claim_docs/SUD Life.docx",
    sections=[
        S(
            "header",
            "Investigation Report",
            [
                F("agency_name", "Investigation agency name", doc="agency_name"),
                F("report_date", "Report Date", type=FieldType.DATE, doc="report_submission_date"),
                F(
                    "report_type",
                    "Report type",
                    type=FieldType.SELECT,
                    options=INTERIM_FINAL,
                    default="Final",
                    doc="report_status",
                ),
                F(
                    "investigator_name",
                    "Investigator's name",
                    prefill="assigned_to_name",
                    doc="field_investigator_name",
                ),
                BANK("reference_number", "Reference number", "krn_no", doc="krn_no"),
                BANK("life_assured_name", "LA's name", "life_assured_name"),
                BANK("policy_number", "Application / policy number", "policy_number"),
                BANK("contact_number", "Contact number", "contact_number", type=FieldType.PHONE),
                BANK("sum_assured", "Sum assured", "sum_assured", type=FieldType.CURRENCY),
                F(
                    "la_present_on_visit",
                    "LA is present on visit",
                    type=FieldType.SELECT,
                    options=["Yes", "No (expired)", "No (absent)"],
                ),
                F(
                    "la_existence_confirmed",
                    "LA's existence confirmed",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "occupation_proposal",
                    "Occupation as per proposal",
                    type=FieldType.SELECT,
                    options=OCCUPATION_TYPE,
                ),
                F("occupation_investigator", "Occupation as per investigator", doc="la_occupation"),
                F("qualification_proposal", "Qualification as per proposal"),
                F(
                    "qualification_investigator",
                    "Qualification as per investigator",
                    doc="la_qualification",
                ),
                F("income_proposal", "Income as per proposal (INR)"),
                F(
                    "income_investigator",
                    "Income as per investigator (INR)",
                    doc="la_annual_income",
                ),
                F("nature_of_duty", "Exact nature of duty"),
                F(
                    "report_conclusion",
                    "Report conclusion",
                    type=FieldType.SELECT,
                    options=POSITIVE_NEGATIVE,
                    required=True,
                    doc="outcome",
                ),
                F(
                    "nominee_name",
                    "Nominee name",
                    prefill="nominee_name",
                    doc="nominee_name",
                ),
                F(
                    "nominee_relationship",
                    "Relationship",
                    prefill="nominee_relation",
                    doc="nominee_relation",
                ),
                F("education_proposal", "Education as per proposal form"),
                F("education_investigator", "Education as per investigator"),
                BANK(
                    "address_proposal",
                    "Address as per proposal",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
            ],
        ),
        S(
            "background",
            "Background of the LA",
            [
                NARRATIVE("background_checks", "Exposure to political or criminal connections"),
            ],
        ),
        S(
            "family_details",
            "Family details",
            [TABLE("family_members", "Family members", FAMILY_COLUMNS, doc="family_members")],
        ),
        S(
            "neighbour_verification",
            "Neighbour verification",
            [
                TABLE("neighbours", "Neighbours", NEIGHBOUR_COLUMNS, doc="neighbours"),
                NARRATIVE(
                    "income_details_family",
                    "Income details of the family and sources (confirmed from whom)",
                ),
                NARRATIVE("health_history", "Health history of the LA (confirmed from whom)"),
                NARRATIVE(
                    "assets_of_la",
                    "Assets of the LA — land / house / vehicle / shop / other "
                    "(confirmed from whom)",
                ),
                NARRATIVE(
                    "local_authority_verification",
                    "Local authority verification (police / panchayat)",
                ),
            ],
        ),
        S(
            "document_verification",
            "Verification of documents",
            [
                NARRATIVE(
                    "documents_verified",
                    "Name of documents with the authority from whom each was verified",
                ),
                F("dc_verification_link", "Death certificate verification link", col_span=12),
                F(
                    "death_certificate_verified",
                    "Death certificate verified",
                    type=FieldType.SELECT,
                    options=["Genuine", "Bogus", "Pending"],
                ),
                F("date_of_death", "Date of death", type=FieldType.DATE, doc="date_of_death"),
                F("cause_of_death", "Cause of death", doc="cause_of_death"),
                F("place_of_death", "Place of death", doc="place_of_death"),
            ],
        ),
        S(
            "observations",
            "Observation and finding of the investigator",
            [
                NARRATIVE("vicinity_remarks", "Vicinity Check", doc="vicinity_remarks"),
                NARRATIVE("overall_remarks", "Additional Remarks", doc="overall_remarks"),
                NARRATIVE("conclusion", "Conclusion", doc="conclusion"),
            ],
        ),
        S(
            "declaration",
            "Declaration",
            [
                F(
                    "fi_name_contact",
                    "Field investigator's name / contact no.",
                    doc="field_investigator_name",
                ),
                F("report_drafted_by", "Investigation report drafted by", doc="report_prepared_by"),
                F(
                    "visit_date",
                    "Investigator's visit date",
                    type=FieldType.DATE,
                    doc="date_of_visit",
                ),
                F(
                    "declaration_accepted",
                    "I declare that all the above details are verified and true to the "
                    "best of my knowledge",
                    type=FieldType.BOOLEAN,
                    required=True,
                    col_span=12,
                ),
            ],
        ),
        photographs_section(
            [
                "Snap taken at the location (with GPS tagging)",
                "LA's signature sample (mandatory)",
                "LA's snap",
                "LA's ID and address proof snap",
                "LA's house snap",
            ]
        ),
        outcome_section(),
    ],
)


# --------------------------------------------------------------------------- #
# 6.18 ICICI Prudential — Landlord / property risk assessment
# --------------------------------------------------------------------------- #
LANDLORD_VERIFICATION = T(
    code="ICICI_LANDLORD",
    name="ICICI Prudential — New Property Acquisition Risk Assessment",
    company="ICICI",
    case_type="LANDLORD_VERIFICATION",
    source_document="death_claim_docs/Land lord death claim.docx",
    description=(
        "Filed by the client under death claims, but its content is a landlord and "
        "branch-premises risk assessment, so it is modelled as its own case type."
    ),
    sections=[
        S(
            "basic_information",
            "Basic Information",
            [
                BANK(
                    "landlord_name",
                    "Name of the Landlord",
                    "life_assured_name",
                    doc="life_assured_name",
                ),
                BANK(
                    "landlord_address",
                    "Address of the Landlord",
                    "address",
                    type=FieldType.TEXTAREA,
                    doc="la_address",
                    col_span=12,
                ),
                F(
                    "property_address",
                    "Address of the Property",
                    type=FieldType.TEXTAREA,
                    required=True,
                    col_span=12,
                ),
                F("landmark", "Landmark near the Property", col_span=12),
                BANK(
                    "landlord_contact",
                    "Contact No of Landlord",
                    "contact_number",
                    type=FieldType.PHONE,
                ),
                F("landlord_email", "Email id of Landlord", type=FieldType.EMAIL),
                F("landlord_alternate_contact", "Alternate Contact No", type=FieldType.PHONE),
            ],
        ),
        S(
            "risk_team_details",
            "Details to be provided by the risk team",
            [
                F(
                    "building_photographs",
                    "Building and proposed branch premise photographs",
                    type=FieldType.SELECT,
                    options=EVIDENCE_STATUS,
                ),
                F(
                    "land_usage",
                    "Land usage as per municipal corporation",
                    type=FieldType.SELECT,
                    options=["Declared Commercial", "Residential", "Industrial", "Mixed"],
                ),
                F(
                    "usage_converted",
                    "Usage converted from residential / industrial to commercial?",
                    type=FieldType.SELECT,
                    options=YES_NO_NA,
                ),
                F(
                    "municipal_approval",
                    "Does the building have municipal corporation approval for commercial space?",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "building_age",
                    "Ageing of the Building",
                    type=FieldType.SELECT,
                    options=["0-2 years", "2-10 years", "10-20 years", ">20 years"],
                ),
                F("main_road_width", "Entrance — width of main road"),
                F("by_lane_width", "Entrance — width of by lane"),
                F(
                    "building_condition",
                    "Condition of Building",
                    type=FieldType.SELECT,
                    options=["Well Maintained", "Acceptable", "Under construction", "Poor"],
                ),
                F(
                    "leakage_seepage",
                    "Are there any signs of leakage or seepage?",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "building_facade",
                    "Façade of building",
                    type=FieldType.SELECT,
                    options=["Excellent", "Good", "Average", "Poor"],
                ),
                NARRATIVE("other_occupants", "Other occupants of the building"),
                NARRATIVE(
                    "adjacent_establishments",
                    "Any restaurant, temple, wine shop, garbage bin etc. adjacent "
                    "to the building or complex (specific details)",
                ),
                F(
                    "distance_railway_bus",
                    "Distance in km from the nearest railway station and bus stop",
                    col_span=12,
                ),
                F(
                    "transport_availability",
                    "Frequent transport availability — taxi / auto from railway station "
                    "or bus stand",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "night_transport",
                    "Public transport system availability at night (after 8 PM)",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
            ],
        ),
        S(
            "hse_standards",
            "HSE Standards",
            [
                F("total_floors", "Total floors in the building"),
                F(
                    "staircase_width",
                    "Does the building have a staircase of 4 feet or more?",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "secondary_exit",
                    "Secondary exit from the building",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "fire_prone_adjacency",
                    "Is the building adjacent to fire-prone establishments "
                    "(manufacturing, petrol pump, fabricators, transformer)?",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    col_span=12,
                ),
                F(
                    "fire_station_distance",
                    "Is the building within 5 km of a fire station?",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "congested_area",
                    "Is the building in a congested area such as a bazaar or old city?",
                    type=FieldType.SELECT,
                    options=YES_NO,
                ),
                F(
                    "flood_riot_history",
                    "Historical profile of the location — prone to flooding, tsunami or riots?",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    col_span=12,
                ),
                NARRATIVE(
                    "firefighting_mechanism",
                    "For premises above 4 floors — in-built firefighting mechanism "
                    "such as a fire hose with a separate water tank",
                ),
            ],
        ),
        S(
            "adverse_check",
            "Adverse Check",
            [
                F(
                    "legal_proceedings_building",
                    "Any known legal proceedings with respect to the building",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    col_span=12,
                ),
                F(
                    "legal_proceedings_landlord",
                    "Any known legal proceedings with respect to the landlord",
                    type=FieldType.SELECT,
                    options=YES_NO,
                    col_span=12,
                ),
            ],
        ),
        S(
            "supervisor_remarks",
            "Supervisor Remarks",
            [
                NARRATIVE(
                    "investigation_findings", "Investigation Findings", doc="overall_remarks"
                ),
                F("agency_name", "Agency Name", doc="agency_name"),
                F(
                    "investigator_name",
                    "Investigator",
                    prefill="assigned_to_name",
                    doc="field_investigator_name",
                ),
                F("agency_contact", "Contact No", type=FieldType.PHONE, doc="agency_contact"),
                F("report_date", "Date", type=FieldType.DATE, doc="report_submission_date"),
            ],
        ),
        photographs_section(
            ["Building exterior photographs", "Proposed office premises photographs"]
        ),
        outcome_section(),
    ],
)


DEATH_CLAIM_TEMPLATES: tuple[T, ...] = (
    BAJAJ_DEATH_CLAIM,
    HDFC_DEATH_CLAIM,
    ICICI_DEATH_CLAIM,
    ICICI_FTI,
    SUD_DEATH_CLAIM,
    LANDLORD_VERIFICATION,
)
