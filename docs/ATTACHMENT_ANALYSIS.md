# Attachment Analysis

> **Source of truth.** Everything in this document was extracted from the files and
> images supplied by the client. Where a generic assumption conflicted with an
> attachment, the attachment won. Nothing here is invented.

Analysis date: 2026-08-27
Scope: architecture pass performed before any implementation.

---

## 1. Inventory of supplied material

### 1.1 Handwritten dashboard specification (Image 1)

Titled **"Virtual Dashboard"**. Transcribed content:

```
Virtual Dashboard

1 - Date, day & Time (Real time)
2 - Overall assignment                 |
3 - Work in Progress cases (WIP)       |  1st  (top strip)
4 - Report in Progress cases (RIP)     |

II -
    Overall Negative Cases     |
    Overall Positive Cases     |  Ratio in %  with graph
    Overall Suspicious Cases   |

    Active Investigators
    Non-Active Investigators
    Active Back office Employee
    Non Active Back office Employee

    Turn around TAT
        In TAT Cases
        Out of TAT Cases
        TAT about to breach Cases
```

### 1.2 Handwritten dashboard specification (Image 2)

Titled **"Screen Shot suggested"**, organisation **VIPL**. Transcribed content:

```
Screen Shot suggested ->
90 days  Data remove

VIPL

Total assignment -> Total Cases
        Day / week / month

Already Created -> Excel / PDF
        overall columns company wise Dashboard

In Progress State ->  work in Prog -> users
                      report in progress
                              |
                          If done
                              |
                      negative / positive / suspicious

Graph -> for negative ...            (export)
```

### 1.3 Raw Excel/CSV header strip (Image 3)

A single header row from the daily file received from the client. Columns, left to right:

| # | Header text (as printed) |
|---|--------------------------|
| 1 | `Co. Name` |
| 2 | `Case Type` |
| 3 | `Month` |
| 4 | `Date` |
| 5 | `Aging` |
| 6 | `KRN No` |
| 7 | `Policy Number` |
| 8 | `Application Number` |
| 9 | `Life_Assured_Name` |
| 10 | `City` |
| 11 | `State` |
| 12 | `Assign To` |
| 13 | `Status` |
| 14 | `Remark/ADD IO ID` |
| 15 | `Pin Code` |
| 16 | `Report Date` |
| 17 | `Completion Date` |
| 18 | `Report Prep By` |

Headers 5, 14, 16, 17 and 18 are visually clipped in the screenshot. They are
implemented under the canonical names above **and** as aliases, so the importer
also accepts the truncated spellings.

### 1.4 Investigation form templates (`investigation_docs/`)

| File | Insurer / client | Report title inside the document | Case type implemented |
|------|------------------|----------------------------------|------------------------|
| `Aditya Birla Life.docx` | Aditya Birla Sun Life | Pre-Issuance Verification Report | `PRE_ISSUANCE` |
| `BAJAJ.docx` | Bajaj Allianz Life | Detailed Verification Report (Confidential) | `PRE_ISSUANCE` |
| `BAXA.docx` | Bharti AXA Life | Pre Claim Report | `PRE_CLAIM` |
| `Bandhan.docx` | Bandhan Life | Pre Issuance Verification Report | `PRE_ISSUANCE` |
| `HDFC Profile check.docx` | HDFC Life | Pre-Claims Investigation Report | `PROFILE_CHECK` |
| `HDFC Pre claim.doc` | HDFC Life | legacy binary `.doc` — see §5.1 | `PRE_CLAIM` |
| `HSBC Canera life.docx` | Canara HSBC Life | Detailed Investigation Report | `PRE_ISSUANCE` |
| `HSBC Canara Mistry Shopping.docx` | Canara HSBC Life | Medical Seeding Report (mystery shopping) | `MEDICAL_SEEDING` |
| `Icici Add.docx` | ICICI Prudential Life | Customer profile verification form | `PROFILE_CHECK` |
| `Icici Payout.docx` | ICICI Prudential Life | Payout Verification Form | `PAYOUT_VERIFICATION` |
| `LMS.docx` | ICICI Prudential Life | Customer Verification Form – New Business | `NEW_BUSINESS_VERIFICATION` |
| `Kotak Life.docx` | Kotak Life | Detailed Investigation [Pre-Claims] Report | `PRE_CLAIM` |
| `Kotak Discreate Cheak.docx` | ICICI Prudential Life (discreet) | Discreet Check | `DISCREET_CHECK` |
| `PNB METLIFE.docx` | PNB MetLife | Scenario-based LA verification | `PRE_CLAIM` |

### 1.5 Death claim form templates (`death_claim_docs/`)

| File | Insurer / client | Report title inside the document | Case type implemented |
|------|------------------|----------------------------------|------------------------|
| `Bajaj death claim.docx` | Bajaj Allianz Life | Investigation Report (Death / Critical illness / Hospital Rider Claim) | `DEATH_CLAIM` |
| `HDFC Death Claim.docx` | HDFC Life | Investigation Report (Death / Critical illness / Hospital Rider Claim) | `DEATH_CLAIM` |
| `ICICI Death Claim.docx` | ICICI Prudential Life | Claim Investigation Report (complete investigation) | `DEATH_CLAIM` |
| `FTI Icici.docx` | ICICI Prudential Life | Claim Investigation Report (field triggered investigation) | `DEATH_CLAIM_FTI` |
| `SUD Life.docx` | Star Union Dai-ichi Life | Investigation Report | `DEATH_CLAIM` |
| `Land lord death claim.docx` | ICICI Prudential Life | Risk Assessment: New Property Acquisition | `LANDLORD_VERIFICATION` |

> **Note on `Land lord death claim.docx`.** The file lives in `death_claim_docs/`
> and the client named it as a death-claim form, but its content is a landlord /
> branch-premises risk assessment (building age, HSE standards, fire safety,
> adverse legal checks). It is therefore modelled as its own case type
> `LANDLORD_VERIFICATION` rather than being forced into the death-claim
> workflow. It is still filed under the Death Claims module because that is where
> the client keeps it.

---

## 2. Vocabulary extracted from the attachments

The system uses the client's own words, not generic CRM words.

| Client term | Meaning in the attachments | Where implemented |
|-------------|---------------------------|-------------------|
| **LA** | Life Assured | field labels throughout |
| **IO** | Investigating Officer / field investigator | `INVESTIGATOR` role |
| **FE** | Field Executive | alias of IO on some forms |
| **KRN** | Key Reference Number (ICICI) | `cases.krn_no`, Excel column 6 |
| **RCD** | Risk Commencement Date | form field |
| **DOD** | Date of Death | `death_claim_details.date_of_death` |
| **DBRCD** | Death Before Risk Commencement Date | key-sensing checkbox |
| **TAT** | Turn Around Time | TAT engine, dashboard |
| **WIP** | Work In Progress | case status |
| **RIP** | Report In Progress | case status |
| **Nexus** | organised fraud operator | key-sensing checkbox |
| **Industry shopping** | same life insured across insurers | key-sensing checkbox |
| **Seeder / SEED** | mystery-shopping decoy patient | medical seeding form |
| **Positive / Negative / Suspicious** | investigation outcome | `cases.outcome` |
| **Interim / Final** | report status | `cases.report_status` |
| **Vicinity check / Discreet check** | neighbourhood enquiry | form section |
| **Profile check** | pre-claim profile verification | case type |
| **Mystery shopping / seeding** | medical-centre integrity check | case type |
| **APL / BPL** | above / below poverty line | standard-of-living option |
| **MER** | Medical Examination Report | seeding form |
| **PMR** | Post Mortem Report | death claim form |
| **MCOD** | Medical Certificate of Cause of Death | death claim form |

---

## 3. Dashboard requirement traceability (Images 1 and 2)

| # | Requirement in image | Image | Backend source | Frontend |
|---|----------------------|-------|----------------|----------|
| 1 | Date, day & time, real time | 1 | server timezone from settings | `LiveClock` widget |
| 2 | Overall assignment | 1, 2 | `GET /dashboard/summary` → `total_assignment` | KPI tile |
| 3 | Work in Progress (WIP) cases | 1, 2 | `summary.wip_cases` | KPI tile |
| 4 | Report in Progress (RIP) cases | 1, 2 | `summary.rip_cases` | KPI tile |
| 5 | Overall Negative cases | 1, 2 | `summary.negative_cases` | KPI tile + donut |
| 6 | Overall Positive cases | 1, 2 | `summary.positive_cases` | KPI tile + donut |
| 7 | Overall Suspicious cases | 1, 2 | `summary.suspicious_cases` | KPI tile + donut |
| 8 | Ratio in % with graph | 1 | `GET /dashboard/outcome-distribution` | donut + % labels |
| 9 | Active investigators | 1 | `summary.active_investigators` (heartbeat) | staff status strip |
| 10 | Non-active investigators | 1 | `summary.inactive_investigators` | staff status strip |
| 11 | Active back-office employees | 1 | `summary.active_back_office` | staff status strip |
| 12 | Non-active back-office employees | 1 | `summary.inactive_back_office` | staff status strip |
| 13 | In TAT cases | 1 | `summary.in_tat` | TAT panel |
| 14 | Out of TAT cases | 1 | `summary.out_of_tat` | TAT panel |
| 15 | TAT about to breach | 1 | `summary.tat_about_to_breach` | TAT panel |
| 16 | Total assignment by day / week / month | 2 | `GET /dashboard/trend?bucket=day\|week\|month` | trend chart + selector |
| 17 | Export Excel / PDF | 2 | `GET /reports/*/export?format=xlsx\|csv`, PDF for case documents | export buttons |
| 18 | Overall columns company-wise dashboard | 2 | `GET /dashboard/company-performance` | company table |
| 19 | In-progress state broken down by user | 2 | `GET /dashboard/investigator-performance` | investigator table |
| 20 | Report in progress → if done → negative / positive / suspicious | 2 | status workflow `RIP → REPORT_SUBMITTED` requires an outcome | workflow guard |
| 21 | Graph for negative | 2 | `GET /dashboard/trend` carries a per-outcome series | trend chart |
| 22 | 90 days data remove | 2 | `data_retention_days` setting (default 90) + purge script | Settings page |

---

## 4. Excel column mapping (Image 3)

Canonical import template `VIPL_STANDARD_V1`. Full validation rules are in
`docs/IMPORT_SYSTEM.md`.

| Excel column | Aliases accepted | Internal field | Type | Required | Validation | In output form |
|--------------|------------------|----------------|------|----------|------------|----------------|
| Co. Name | Company, Company Name, Insurer | `company_code` (resolved) | lookup | yes | must resolve to an active company | yes — selects the template |
| Case Type | Type, Case_Type | `case_type_code` (resolved) | lookup | yes | must resolve to an active case type | yes — selects the template |
| Month | — | `received_month` | text | no | free text, normalised to `MMM-YYYY` when parseable | no |
| Date | Received Date, Allocation Date | `received_at` | date | yes | `dd-mm-yyyy`, `dd.mm.yyyy`, `dd/mm/yyyy`, ISO, Excel serial | yes |
| Aging | Ageing, Agi | `aging_days` | int | no | >= 0; recomputed by the TAT engine | no |
| KRN No | KRN, Key Reference Number | `krn_no` | text | no | unique per company when present | yes |
| Policy Number | Policy No., Contract No | `policy_number` | text | conditional | policy **or** application number required | yes |
| Application Number | Application No., App No, Proposal No | `application_number` | text | conditional | see above | yes |
| Life_Assured_Name | Life Assured Name, LA Name, Insured Name | `life_assured_name` | text | yes | 2..200 characters | yes |
| City | — | `city` | text | no | — | yes |
| State | — | `state` | text | no | — | yes |
| Assign To | Assigned To, IO Name | `assigned_to_id` (resolved) | lookup | no | matched to staff by employee code, email, then full name | yes |
| Status | — | `status` | enum | no | mapped through the status synonym table | no |
| Remark/ADD IO ID | Remark, Remarks, ADD IO ID | `import_remark` | text | no | — | no |
| Pin Code | Pincode, PIN | `pin_code` | text | no | 6 digits when present | yes |
| Report Date | Rep. Date | `report_date` | date | no | date parser | yes |
| Completion Date | Completion Dt | `completion_date` | date | no | date parser | yes |
| Report Prep By | Report Prepared By | `report_prepared_by` | text | no | — | yes |

**Duplicate key.** Derived from the sample: a row is a duplicate when
`(company, krn_no)` matches an existing case, or — when KRN is blank —
`(company, policy_number, application_number, life_assured_name)` matches.
The strategy is configurable per import template rather than hard-coded.

---

## 5. Document-generation mapping

Each supplied `.docx` is registered as a **document template** bound to
`(company, case_type, version)`. Generation uses `docxtpl`, which preserves the
original Word layout — tables, headings, spacing, logos, signature blocks — and
substitutes only placeholder tags.

The uploaded originals are *filled specimens* of real cases, not blank templates
carrying `{{ }}` tags. The system therefore keeps them in two forms:

1. **`storage/document_templates/original/`** — the client's untouched file, kept
   forever and never overwritten. Every generated document records which original
   it derived from.
2. **`storage/document_templates/tagged/`** — a generated, tagged copy in which
   the specimen values found in the original have been replaced by
   `{{ field_key }}` placeholders. `scripts/tag_templates.py` performs the
   conversion and writes a report of every substitution, so the mapping stays
   auditable.

Placeholders in use (superset; each template uses the subset its layout contains):

```
{{ agency_name }}            {{ field_investigator_name }}   {{ fi_contact_number }}
{{ assignment_date }}        {{ report_submission_date }}    {{ tat_days }}
{{ company_name }}           {{ case_number }}               {{ krn_no }}
{{ policy_number }}          {{ application_number }}        {{ product_name }}
{{ sum_assured }}            {{ premium_amount }}            {{ rcd }}
{{ life_assured_name }}      {{ la_dob }}                    {{ la_age }}
{{ la_gender }}              {{ la_marital_status }}         {{ la_qualification }}
{{ la_occupation }}          {{ la_annual_income }}          {{ la_address }}
{{ city }}                   {{ state }}                     {{ pin_code }}
{{ contact_number }}         {{ alternate_contact }}         {{ email_id }}
{{ nominee_name }}           {{ nominee_relation }}          {{ nominee_dob }}
{{ claimant_name }}          {{ claimant_relation }}         {{ claimant_age }}
{{ date_of_death }}          {{ place_of_death }}            {{ cause_of_death }}
{{ date_of_visit }}          {{ time_of_visit }}             {{ person_met }}
{{ relation_with_la }}       {{ vicinity_remarks }}          {{ overall_remarks }}
{{ conclusion }}             {{ outcome }}                   {{ report_status }}
{{ family_members }}         {{ neighbours }}                {{ hospitals }}
{{ documents_collected }}    {{ other_policies }}            {{ generated_on }}
```

`family_members`, `neighbours`, `hospitals`, `documents_collected` and
`other_policies` are **row collections** rendered into the repeating table rows
that every one of these forms contains.

Versioning: a completed case permanently stores `document_template_id` and its
version. Uploading a new revision of an insurer form creates version *n+1*;
already-completed cases keep rendering against the version they were completed
under.

### 5.1 Legacy `.doc` file

`investigation_docs/HDFC Pre claim.doc` is a **binary Word 97-2003 file**, not an
OOXML package, so `python-docx` / `docxtpl` cannot read it. Handling:

* it is registered in `document_templates` with `status = NEEDS_CONVERSION`;
* the admin Document Templates screen shows the banner *"Legacy .doc — re-save as
  .docx to enable DOCX generation"* together with an upload control;
* generation for that template falls back to the built-in PDF renderer until a
  `.docx` is supplied.

This is a limitation of the source file, not of the system.

---

## 6. Form structures extracted per template

Section names below are the ones printed in the client's documents. They are
seeded verbatim into `form_sections`; field labels are seeded into `form_fields`.

### 6.1 Aditya Birla Sun Life — Pre-Issuance Verification Report
1. **Basic Information** — Policy No., Application No., Name, Address, Contact Number, Alternate Address, Date of Investigation
2. **Residence Visit Details – Direct Check** — Person Met, Relation, Period of stay, Ownership of House, Residence Type, Locality, DOB, Education, Marital Status, Family Members, Earning Members, Occupation, Income, Neighbors Confirmation, Negative Habits, Overall Health, Negative Information, FE Remarks
3. **Discreet / Vicinity Check – Summary** — Nearby shop/office reference (name/designation/contact), Financial Standing of the Life Assured, Overall feedback, Negative feedback, Any disparity between vicinity and direct check
4. **Report Prepared By** — Verification agency name and code, Field executive name
5. **Photographs** — Life Assured / Residence / Vicinity

### 6.2 Bajaj Allianz Life — Detailed Verification Report (Confidential)
1. **Header** — Investigation agency name, Investigation type, Application/Policy number, Case entrusted date, Date of verification, Time of investigation, Report submission date, Verification done with
2. **(A) Profile of LA** — 11 numbered rows, each with *value / matching with proposal form / output*: Spoke with, Life Assured Name, DOB-Age, Place of Birth, Marital Status, Education Qualification, Occupation Type, Income per annum, Employer/Trade name, Other life or health insurance, Details of other insurance
3. **(B) Habits & Health** — Smoking, Drinking, Hospitalised in last 3 years, Family physician details
4. **(C) Medication status** — under treatment / medication details
5. **(D) Family Details** — members count & relation, number of dependents, total family income, family health history, family life/health policy, political relation
6. **(E) Important Details (as per Proposal Form)** — Contact & alternate no., Email IDs, Permanent address, Communication address, Type of address, Nominee name/relation/contact, Nominee DOB, Nominee occupation & income, Sum assured/premium/mode, Policy term & PPT, Who pays the premium
7. **(F) Other Observations** — face-matching score with the proposal form, and other observations

### 6.3 Bharti AXA Life — Pre Claim Report
1. **Brief details (as per company)** — Type of claim, Life Insured, Policy no, Age/DOB, Address, Date of Policy, Report Submission Date
2. **Detailed report questionnaire** — six numbered questions: LA and family traceable at address, LA alive/healthy, financial and health condition justifying the insurance, age as proposed, other notable findings, details of hospital checks
3. **Detailed finding** — Vicinity Check, Overall Observation

### 6.4 Bandhan Life — Pre Issuance Verification Report
1. **Header** — Report Type, Investigation Date, Application No, RCD, INV Received Date, Report Sent Date
2. **Life assured** — Name, Company Provided Address, Contact/Alternate, LA met in person, If died DOD, Existence of address, Existence of LA, DOB, Qualification, Occupation, Nature of Work, Employer, Income, Standard of Living, Health Condition, Negative Habits, Pre-existing illness, Call History, Evidence collected, Audio/Video confirmation, Location photo with geo tagging, Existing policy details
3. **Findings** — Vicinity Findings, Overall Findings, Summary of Findings, Investigation Final Remark
4. **Sign-off** — Verification agency and owner name, Field officer details, geo-tagged photographs, declaration

### 6.5 HDFC Life — Pre-Claims Investigation Report (profile check)
1. **Investigator details** — Agency name, Field investigator name, FI contact number, Assignment date, Report submission date, Time taken (TAT)
2. **Investigation outcome** — Policy/Application number, Outcome (Positive/Negative/Suspicious), Specify (Life Existed / Non Existed / Terminally ill or older lives / Death before issuance / Third-party investments / Financially very poor profile / Non disclosure / Non contactable / Others)
3. **Policy / proposal details** — LA Name, LA DOB
4. **Personal details of the insured** — Yes/No grid: address traceable, did LA meet, LA salaried, LA self-employed, LA looks healthy, consumes alcohol, LA educated, met any family member
5. **Vicinity check** — narrative plus a table of persons met (name, relation, contact, address)
6. **Second Yes/No grid** — LA identified, LA alive, adversity on health, adverse habits, salaried, self-employed
7. **Investigation agency overall findings** — narrative
8. **Documents procured / collected** — Age proof, Occupation and income proof, Customer live photo with house photo, Medical evidence, Nominee KYC, Death certificate and Anganwadi certificate if expired, Declarations

### 6.6 Canara HSBC Life — Detailed Investigation Report
Proposal No., Life Assured Name, Allocation date, Verification Type, Address, Mobile No., Alternate number/email, Verification date, Report overall status, Verifier name, ID card seen, Address proof seen, Name of person met, Relation with LA, LA DOB, Health condition and lifestyle, Disease details if unhealthy, History of medical investigation/surgery, Family medical history, Treatment papers/audio/video, Policies other than Canara HSBC, Residence locality and type, Residence ownership, Years at current residence, Financial status, Family members and details, Education, Employment category, Organisation name and nature of work, Self-employed firm details, Annual income, Nominee name and relation, Vicinity check details.
Narrative blocks: Discreet Check, Residence Visit, Health and Habits, Family Details, Investigation Findings, Note.
Photo blocks: LA house / LA or met person / KYC / field executive selfie — all geo-tagged.

### 6.7 Canara HSBC Life — Medical Seeding Report (mystery shopping)
1. **Seeding header** — Date of seeding, Name of medical centre, Location, Category of medical done, Name of the individual who went for the medical
2. **Mystery-shopping questionnaire** — 20 yes/no and multiple-choice observations: identification at reception, authorisation letter and photo ID checked, response at reception, time taken, left unattended, lab ambience, proper sample collection room, blood drawn by a qualified technician, disposable syringes, sample transferred to marked containers, MBBS doctor performed the MER, doctor offered to convert a negative report after inducement, examination couch clean, BP readings taken, who did the measurements, readings revealed, copy of reports provided, weight machine maintained, height and weight properly measured, toilets clean, informed to leave
3. **Seeder details** — Seed name, Father's name, DOB
4. **Medical activity details** — Height measured, Weight measured, Chest inspirations, Chest expirations, Blood sample given, Mixed water in urine sample, Declared alcoholic, Declared smoker, Declared any other medical suffering — each with Y/N plus reading/remarks
5. **Family history table** — member, living/dead, age, health status, age at death, cause of death, year of death
6. **Any other observations** — narrative

### 6.8 ICICI Prudential — Customer profile verification form
Assignment date, Agency name, Contact number, Report submission date, Decision, LA met, Evidence available, Evidence details, Remarks; Application no., Policy no, Issue date, Product, Sum assured, Premium amount; Case details (Proposer name, LA name, communication address, permanent address, contact number); Proposal verification (locality, existence established, LA met, whom did you meet, relationship, DOB, identity proof, address proof, education, health, habits, quantity/years, physical appearance, handicap, existing insurance, live photo, residence photo); Proposer details (occupation, company name, income, income proof, family members, earning members, office/shop photo, house type); Vicinity check (personal details as per vicinity, income details as per vicinity, persons-met table, hospital/doctor/chemist table, conclusions); DBRCD death certificate / cemetery verification block; Other insurance details table; Family history table; Overall remarks (discreet check, overall remarks); geo-tagged photographs for each visit.

### 6.9 ICICI Prudential — Payout Verification Form
Policy Number*, KRN, Customer Name*, Assignment Request Given*, Allocation Date*, Father Name*, Date and time of field visit*, Nominee Name*, Nominee DOB*, Date and time of appointment call; Existing address details* (address, pin code, landmark, landline and extension, e-mail 1, e-mail 2, mobile number*) and the matching New Address block; Third-party confirmation block; Details from family representatives (name, relationship, contact*, comments); Vicinity check details (name, address, contact*); Residence status (type of house, traceability, location, ownership*); Contactability (contacted at address, contacted over phone); Final remarks; Declaration; Photographs*; Final status.
Fields marked `*` are mandatory in the client's form and are enforced as required in the template.

### 6.10 ICICI Prudential — Customer Verification Form – New Business (LMS)
Application Number, Customer Name, Vendor Name, KRN, Date of Visit, Time of Visit; two-column checklist: Contactability / Address Traced, LA Existence Verified / Duration of Stay, Applied for Policy / Occupation, Met Policy Holder / Designation, Type of House / Company Name, Location / Annual Income, Ownership / Behavioural issue, Address Verified / Education, PAN no / Aadhar No, Physical Observation / Marital Status; Details obtained during vicinity check (name of person met, address of person met, contact no, vicinity check remarks); Post office details when the address is not traceable (postal official name, contact number, post office name, post office photo Y/N); Final remarks — Discreet Check, Overall Remarks; Supporting documents.

### 6.11 Kotak Life — Detailed Investigation [Pre-Claims] Report
Investigator details (agency, field investigator, contact, assignment date, report submission date, TAT); Decision (Positive/Negative) and specify; Proposal/policy details (App No, Policy No, Policy issued date, Sum insured, Policy duration); **Proposal verification matrix** — for each of Name, DOB/Age, Income, Occupation, Work place address, Health and hospitalisation, Marital status, Qualification, Address, Nominee, PEP, Hazardous hobbies: *In proposal form / During profile check / Discrepancy noted / Evidence received / Specify evidence*; Family history table (name, relation, age, occupation, income, health, KYC proof); Other policy and family insurance table; Vicinity check table plus findings; Workplace check table plus salaried and self-employed blocks; Newspaper / internet check; Investigation agency overall findings; Documents procured/collected; visit photo blocks.

### 6.12 ICICI Prudential — Discreet Check
Type of check plus KRN, Report submission date; Life assured details matrix (Name, DOB/age, Address, Education — *as per proposal* versus *if different from proposal*); Complete investigation report — Field investigation summary, Financial status, Residential check, Health conditions, Conclusion; Enclosures (live snaps, neighbour videos, supporting); Any relevant details not mentioned above; Locality and house photos.

### 6.13 PNB MetLife — Scenario-based verification
Application No, Investigating agency details, FE name, Date of case receipt, Date of visit, Date of report, Overall status; LA name / address / mobile / status;
**Scenario 1 — Life Assured met**: 1.1 financial status, 1.2 physical appearance checked, 1.3 neighbour check done, 1.4 photographs collected, special remarks.
**Scenario 2 — LA alive and unhealthy**: 2.1 disease/illness with duration, 2.2 financial status, 2.3 physical appearance/abnormality, 2.4 vicinity/neighbour check feedback, 2.5 photographs.
**Scenario 3 — LA deceased**: 3.1 disease/illness, 3.2 financial status, 3.3 physical appearance, 3.4 vicinity check, 3.5 photographs of house/nearby landmark, 3.6 date and place of death.
Plus the procedural blocks *LA not met at first attempt* and *LA refused to meet / not traced*, then Vicinity Check and Overall Remark narratives.

### 6.14 Bajaj Allianz Life and HDFC Life — Death claim investigation report
Both insurers use the same client format:
1. **Report status** — Interim/Final, Investigation outcome (negative/positive)
2. **Claim details** — Policy No., Type of claim, Name of LA, DOB/Age of LA, Occupation of LA, Income of LA, State/City of LA, Risk comm. date, Date of Death, Sum Assured, Cause of Death, Place of Death, Name of Claimant, Age of Claimant, Relation with LA, Occupation of Claimant, Income of Claimant, State/City of Claimant, Contact no., Case assignment date, 1st report submission date, Final report submission date, Type of negative evidence collected, Source of negative evidence, Any RTI applied, RTI status
3. **Life Assured's profile** — Name, DOB, Age, DOD, Marital status, Occupation, Annual income, Qualification, Address, Claimant/beneficiary relationship, plus a discrepancy column
4. **Family details and history** table — name, age, relationship with LA, occupation and income, other insurance
5. **Nominee details and statement**
6. **LA residence check** — standard of living (APL/BPL/high income group), KYC and contact number, past and present medical records, annual income confirmation, purpose for insurance, other insurance details
7. **Neighbourhood check** — five to six people, each with name / place (residence or workplace) / contact number, plus a summary
8. **Doctor, hospital, pathology and chemist checks** — tables of name, contact person, location, contact no, date of visit, evidence
9. **Occupation / workplace check** — salaried block and self-employed block
10. **Police verification** — FIR summary, PMR summary, viscera report, final police report (mandatory for accidental, suicide, poisoning and murder cases)
11. **Cremation and burial** — death register / cremation slip
12. **Document verification** — age proof, death certificate by issuing authority
13. **Newspaper / internet check**
14. **Panchayat / village touch points** — Panchayat Secretary, Gram Pradhan/Sarpanch, BDO, Circle Officer, Anganwadi Sevika/ANM/ASHA worker, PHC/CHC, other (Police Patil / Mamledar / Village officer / Councillor)
15. **Advisor check** — advisor detail, contact, relationship with LA, sourcing details, feedback
16. **Agency overall remarks and conclusion**
17. **Major suspicion**
18. **List of documents collected** — type, source of procurement, verified by, dates
19. **Interim/final report tracking and re-actionables**

### 6.15 ICICI Prudential — Claim Investigation Report (complete)
1. **Claim information** — Type of investigation, Key reference number, Contract No, Life Assured's name, Sum assured, Proposer's/Claimant's name, Risk commencement date, Product, Investigating agency name and contact, Field investigator name and contact, Allocation date, Date of report submission
2. **Key sensing of the case** — a fixed checklist, each with *Yes/No/Suspected*, *details of mismatch and source*, *evidence details*: Profile Mismatch, Medical non-disclosure, Death before issuance, Impersonation, Forged/tampering of documents, Nexus involvement, Industry shopping, Any other adverse findings, No adverse findings
3. **Part 1 — checks of proposal/claim form details** — matrix of Name, Address, DOB, Age, Marital status, Occupation, Annual income, Education, Other life/health insurance, LA photograph, LA KYC, Date of death, Place of death, Cause of death, Nominee's name, Nominee's relationship, Any other mismatch — each with *as per investigation / mismatch noted / information source / evidence procured*
4. **Family details** plus an age-proof collection grid (Parivar Card, Voter ID, Ration Card, Aadhaar, PAN)
5. **LA residence check** — standard of living, KYC and contact, medical records, annual income with supporting documents, purpose for insurance, other insurance
6. **Part 2 — detailed investigation** — discreet check at residence and workplace (five to six people), family doctor check, hospital check, employment checks
7. **Death confirmation** — death certificate verification, cremation documents, Anganwadi/ANM/Ward member/Sarpanch/Gram Sachiv/BLO/BDO check, last treating hospital with MCOD/death summary
8. **Additional checks for unnatural death** — FIR/GD, postmortem, viscera/chemical analysis, final police report, court order/charge sheet, media checks
9. **Nexus / negative location observations**
10. **Checklist of documents and photographs** — identity confirmation, salaried block, self-employed block, farming block, claimant-related checks
11. **RTI summary** table — reason for filing, authority detail, filed date, POD/reference number, tentative date of response
12. **Re-actionables** — first / second / third reassignment with reason and response
13. **Declaration**

### 6.16 ICICI Prudential — FTI (field triggered investigation) claim report
A lighter version of 6.15: Claim information; Part 1 — LA details *as per nominee/family members* versus *as per vicinity*; death-related findings (date, place, cause) with mismatch and evidence columns; family details including the nominee; KYC collected for LA, relationship proof, KYC for nominee; Part 2 — neighbour grid, death confirmation (death certificate verification, cremation/burial ground documents, met person), additional checks for unnatural death; summary and conclusion checklist (exact date and cause of death, family statements, neighbour statements, occupation verification, past medical history, residence pictures, other policies, PM and FIR copy, RTI, suicide ruled out); key sensing table.

### 6.17 SUD Life — Investigation Report
Header grid (agency name, report date, report type, investigator name, reference number, LA name, application/policy number, contact number, sum assured, LA present on visit, LA existence confirmed, occupation as per proposal versus investigator, qualification as per proposal versus investigator, income as per proposal versus investigator, exact nature of duty, report conclusion, nominee name, relationship, education as per proposal versus investigator, address as per proposal); Background of LA (exposure to political/criminal connections); Family details table; Neighbour verification table (name, address, contact no., remark); Income details of family and sources; Health history of LA; Assets of LA (land/house/vehicle/shop/other); Local authority verification (police/panchayat); Verification of documents including the death-certificate verification link; Observation and finding of investigator (vicinity check, additional remarks, conclusion); Conclusion and reason; GPS-tagged snap blocks; Declaration with drafted-by and visit date.

### 6.18 ICICI Prudential — Landlord / property risk assessment
Basic information (landlord name, landlord address, property address, landmark near the property, contact no, email, alternate contact); Details to be provided by the risk team (building and premises photographs, land usage as per municipal corporation, usage converted from residential/industrial to commercial, municipal approval for commercial space, ageing of the building, entrance — width of main road and by-lane, condition of building, signs of leakage or seepage, façade of building, other occupants of the building, adjacent restaurant/temple/wine shop/garbage bin, distance from nearest railway station and bus stop, frequent transport availability, night public transport after 8 PM); HSE standards (total floors, staircase of four feet or more, secondary exit, adjacency to fire-prone establishments, distance from fire station, congested area, flood/tsunami/riot-prone history, in-built firefighting mechanism for buildings above four floors); Adverse check (legal proceedings against the building, legal proceedings against the landlord); Supervisor remarks and investigation findings; agency sign-off.

---

## 7. Status vocabulary derived from the attachments

```
Imported → Unassigned → Assigned → Accepted → WIP (Work In Progress)
        → Field Investigation → Documents Pending → RIP (Report In Progress)
        → Report Submitted → Under Review → Correction Required
        → Verified → Completed
```

plus the terminal states `Rejected` and `Cancelled`.

`WIP` and `RIP` come straight from Image 1 and Image 2 and are first-class
statuses, not derived labels.

Outcome is a separate axis, set when the report is submitted:
`Positive | Negative | Suspicious` (Images 1 and 2), alongside
`Report status = Interim | Final` from the Bajaj / HDFC / SUD / Bandhan forms.

---

## 8. Requirement traceability summary

| Client requirement | Attachment | System module | Implementation |
|--------------------|-----------|---------------|----------------|
| Real-time date/day/time | Image 1 #1 | Dashboard | `LiveClock`, timezone from settings |
| Overall assignment KPI | Images 1, 2 | Dashboard | `/dashboard/summary` |
| WIP / RIP counters | Images 1, 2 | Dashboard, Case workflow | dedicated case statuses |
| Positive / Negative / Suspicious with % and graph | Images 1, 2 | Dashboard | `/dashboard/outcome-distribution` |
| Active versus non-active investigators | Image 1 | Staff | heartbeat-based online status |
| Active versus non-active back-office employees | Image 1 | Staff, HR | `staff_category` = FIELD / BACK_OFFICE |
| In TAT / Out of TAT / About to breach | Image 1 | TAT engine | `due_at`, `tat_state` computed server-side |
| Day / week / month trend | Image 2 | Dashboard | `/dashboard/trend?bucket=` |
| Company-wise dashboard columns | Image 2 | Dashboard, Reports | `/dashboard/company-performance` |
| In-progress by user | Image 2 | Dashboard, Reports | `/dashboard/investigator-performance` |
| Excel / PDF export | Image 2 | Reports, Documents | XLSX/CSV export, DOCX/PDF generation |
| 90-day data removal | Image 2 | Settings, Admin | `data_retention_days`, purge script |
| Daily Excel intake | Image 3 | Import | `VIPL_STANDARD_V1` template |
| Bank-supplied fields must auto-fill | Image 3 + forms | Import, Forms | provenance-tagged prefill |
| Company-specific investigation forms | 14 `.docx` | Form templates | seeded templates per company |
| Company-specific death claim forms | 6 `.docx` | Form templates | seeded templates per company |
| Completed case → client document | all `.docx` | Document generation | `docxtpl` with version pinning |
| Assign case to investigator | Image 3 `Assign To` | Assignment | assignment aware of online status |
| Audit of everything | stated requirement | Audit | `audit_logs` on every mutation |
| Staff online/offline green/red | stated requirement | Staff | heartbeat plus threshold setting |
| Super Admin from environment | stated requirement | Auth | `.env` bootstrap, Argon2 hash |
| HR module | stated requirement | HR | employees, departments, designations, attendance, leave |
