# Import mapping notes

The importer resolves spreadsheet headers to internal fields through the
`VIPL_STANDARD_V1` import template, which lives in the database
(`import_templates` / `import_column_mappings`). Header text is matched
case-insensitively and ignoring punctuation and spacing, so
`Life_Assured_Name`, `Life Assured Name` and `life assured name` all match.

## Columns

| Excel column | Internal field | Type | Required | Also accepted |
|--------------|----------------|------|----------|---------------|
| Co. Name | `company_code` | text | yes | Company, Company Name, Insurer, Co Name, Client |
| Case Type | `case_type_code` | text | yes | Type, Case_Type, Assignment Type |
| Month | `received_month` | text | no | — |
| Date | `received_at` | date | yes | Received Date, Allocation Date, Assignment Date, Case Date |
| Aging | `aging_days` | int | no | Ageing, Agi, Age Days |
| KRN No | `krn_no` | text | no | KRN, Key Reference Number, KRN Number, Reference No |
| Policy Number | `policy_number` | text | no | Policy No, Policy No., Contract No, Contract Number |
| Application Number | `application_number` | text | no | Application No, Application No., App No, Proposal No, Application Numb |
| Life_Assured_Name | `life_assured_name` | text | yes | Life Assured Name, LA Name, Insured Name, Customer Name, Name of LA |
| City | `city` | text | no | — |
| State | `state` | text | no | — |
| Assign To | `assigned_to` | text | no | Assigned To, IO Name, Investigator, Allocated To |
| Status | `status` | text | no | Case Status |
| Remark/ADD IO ID | `import_remark` | text | no | Remark, Remarks, ADD IO ID, Remark/ADD IO II |
| Pin Code | `pin_code` | text | no | Pincode, PIN, Pin |
| Report Date | `report_date` | date | no | Rep Date, Rep. Date |
| Completion Date | `completion_date` | date | no | Completion Dt, Closed Date, Completion Da |
| Report Prep By | `report_prepared_by` | text | no | Report Prepared By, Prepared By, Report Prep B |
| Address | `address` | text | no | Full Address, LA Address |
| Contact Number | `contact_number` | text | no | Mobile, Mobile No, Contact No, Phone |
| Alternate Contact | `alternate_contact` | text | no | Alternate No, Alt Contact |
| Email | `email_id` | text | no | Email ID, E-mail |
| Product | `product_name` | text | no | Product Name, Plan |
| Sum Assured | `sum_assured` | decimal | no | SA, Sum_Assured |
| Premium Amount | `premium_amount` | decimal | no | Premium |
| RCD | `risk_commencement_date` | date | no | Risk Commencement Date, Risk Comm Date |
| Nominee Name | `nominee_name` | text | no | Nominee |
| Nominee Relation | `nominee_relation` | text | no | Relation |
| Date of Death | `date_of_death` | date | no | DOD, Death Date |
| Place of Death | `place_of_death` | text | no | — |
| Cause of Death | `cause_of_death` | text | no | — |
| Claimant Name | `claimant_name` | text | no | Nominee/Claimant |
| Claimant Relation | `claimant_relation` | text | no | — |

## Rules

* **Dates** are read day-first: `05-08-2026` is 5 August 2026. `dd-mm-yyyy`,
  `dd/mm/yyyy`, `dd.mm.yyyy`, ISO dates and Excel serial numbers all work.
* **Company** and **Case Type** must resolve to an active record. Both accept
  the aliases listed above, so `Bajaj`, `Bajaj Allianz` and `BAJAJ` all map to
  the same company.
* Either **Policy Number** or **Application Number** is required.
* **Assign To** is matched to staff by employee code, then email, then full
  name. If no match is found the case is imported unassigned and the row is
  flagged as a warning, not an error.
* **Status** is mapped through a synonym table (`WIP`, `Work in progress`,
  `In Progress` all become WIP). Unrecognised values produce a warning and the
  case is created as Imported.
* **Duplicates** are detected on `(Co. Name, KRN No)`; when KRN is blank the
  fallback key is `(Co. Name, Policy Number, Application Number,
  Life_Assured_Name)`.
* Uploading a file whose SHA-256 checksum matches an already-committed batch
  is refused, so the same file cannot be imported twice by accident.
* Extra columns are preserved in the row snapshot and ignored for mapping.

## Workflow

```
Upload -> Detect headers -> Validate structure -> Preview -> Map columns
       -> Validate data -> Show errors -> Confirm -> Create cases -> Summary
```

Rejected rows can be downloaded as a workbook containing the row number, the
original data and the error message.
