"""Turn the client's filled specimen forms into reusable ``{{ tag }}`` templates.

The insurer documents supplied with this project are completed real reports. This
script writes a *tagged copy* of each one into
``storage/document_templates/tagged/`` with the specimen values replaced by Jinja
placeholders, leaving the original layout — tables, headings, spacing, logos,
signature blocks — exactly as the client drew it. The originals in
``storage/document_templates/original/`` are never modified.

Usage (from ``backend/``)::

    python -m scripts.tag_templates            # tag everything, update the DB
    python -m scripts.tag_templates --dry-run  # report only, write nothing
    python -m scripts.tag_templates --file "BAJAJ.docx"

Every substitution is printed, so the mapping from specimen value to placeholder
is auditable.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.config import PROJECT_ROOT, settings  # noqa: E402
from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.documents import docx_renderer  # noqa: E402
from app.documents.tagger import tag_document  # noqa: E402
from app.models.document import DocumentTemplate  # noqa: E402
from app.models.enums import DocumentTemplateStatus  # noqa: E402
from app.utils.files import relative_to_storage  # noqa: E402

#: Specimen value -> placeholder, per source document.
#:
#: Only unambiguous, short values are tagged automatically. Long narrative
#: paragraphs are left in place: an administrator replaces those with
#: ``{{ overall_remarks }}`` / ``{{ vicinity_remarks }}`` / ``{{ conclusion }}``
#: once, in Word, and re-uploads the file as a new template version.
REPLACEMENTS: dict[str, dict[str, str]] = {
    "Aditya Birla Life.docx": {
        "9927720": "{{ policy_number }}",
        "LA54043695": "{{ application_number }}",
        "MRS. ABDA  BEGUM": "{{ life_assured_name }}",
        "A-841 A BLOCK-N EAR NEELGIRI-COLUCKNOW UTTAR PRADESH 226016":
            "{{ la_address }}",
        "9415142969": "{{ contact_number }}",
        "20-07-2025": "{{ date_of_visit }}",
        "6/8/1975": "{{ la_dob }}",
        "Virtual007": "{{ agency_name }}",
        " Vijay": " {{ field_investigator_name }}",
    },
    "BAJAJ.docx": {
        "Virtual Investigation Services": "{{ agency_name }}",
        "6167374565/ 0657197410": "{{ application_number }} / {{ policy_number }}",
        "21-08-2026": "{{ case_entrusted_date }}",
        "25-08-2026": "{{ date_of_visit }}",
        "04:15 PM": "{{ time_of_visit }}",
        "26-08-2026": "{{ report_submission_date }}",
        "Ajay Yadav": "{{ person_met }}",
        "Pooja": "{{ life_assured_name }}",
        "9621161085": "{{ contact_number }}",
    },
    "BAXA.docx": {
        "Mohd. Zameer": "{{ life_assured_name }}",
        " 503-9838817": " {{ policy_number }}",
        "28-12-2023": "{{ rcd }}",
        "18-06-2026": "{{ report_submission_date }}",
        "S/O RAISUDDIN 417, MOHALLA SHER MOHAMMAD PILIBHIT GOVERNMENT INTER CO  "
        "CITY_CODE 262001 State UTTAR PRADESH": "{{ la_address }}",
    },
    "Bandhan.docx": {
        "ALI000001078039": "{{ application_number }}",
        "21-07-2026": "{{ date_of_visit }}",
        "18-07-2026": "{{ assignment_date }}",
        "23-07-2026": "{{ report_submission_date }}",
        "Akarsh": "{{ life_assured_name }}",
        "Vill Bhikhapur Ayodhya Uttar Pradesh India 224001 City Ayodhya State "
        "Uttar Pradesh pin_code 224001": "{{ la_address }}",
        "8400003587": "{{ contact_number }}",
        "01-07-2004": "{{ la_dob }}",
        "Virtual007 Investigation": "{{ agency_name }}",
        "Anoop Kumar Pathak": "{{ field_investigator_name }}",
    },
    "HDFC Profile check.docx": {
        "Virtual Investigation 007": "{{ agency_name }}",
        "Vivek": "{{ field_investigator_name }}",
        "9151611161": "{{ fi_contact_number }}",
        "15-08-2026": "{{ assignment_date }}",
        "26-08-2026": "{{ report_submission_date }}",
        "11 days": "{{ tat_days }}",
        "PP000572 / 1001175757": "{{ policy_number }} / {{ application_number }}",
        "KhanFiroj": "{{ life_assured_name }}",
        "01-01-1986": "{{ la_dob }}",
    },
    "HSBC Canera life.docx": {
        "9103112313": "{{ application_number }}",
        "Mr. Raveekant": "{{ life_assured_name }}",
        "20-08-2026": "{{ allocation_date }}",
        "22-08-2026": "{{ date_of_visit }}",
        "S/O: Mahesh,219, Nagla Sanja, Akosh, Chhata, Mathura Pin Code 281301 "
        "State Uttar Pradesh": "{{ la_address }}",
        "6395141514": "{{ contact_number }}",
        "01-01-1976": "{{ la_dob }}",
        "Navratan": "{{ field_investigator_name }}",
    },
    "HSBC Canara Mistry Shopping.docx": {
        "22-08-2026": "{{ date_of_visit }}",
        "City Care Parag Pathology and Diagnostic Centre-Moradabad":
            "{{ medical_centre_name }}",
        "Mr. Kushal Kumar": "{{ seed_name }}",
        "Mr. Rajendra Singh": "{{ seed_father_name }}",
        "10-08-1995": "{{ seed_dob }}",
    },
    "Icici Add.docx": {
        "29/06/2026": "{{ assignment_date }}",
        " Virtual OO7 Investigation Pvt. Ltd.": " {{ agency_name }}",
        "9161022060": "{{ agency_contact }}",
        "24/07/2026": "{{ report_submission_date }}",
        "   K9588053": "   {{ policy_number }}",
        "25/04/2026": "{{ issue_date }}",
        "8333/- monthly": "{{ premium_amount }}",
        "GEETA AHIRWAR": "{{ life_assured_name }}",
        # A specimen list entry with no home in the table pass.
        "Pooja Medcial": "{{ hospitals }}",
        "7827114949": "{{ contact_number }}",
        "01-01-1989": "{{ la_dob }}",
    },
    "Icici Payout.docx": {
        "Virtual Investigation Services": "{{ agency_name }}",
        "19681199": "{{ policy_number }}",
        "1161591": "{{ krn_no }}",
        "ABHINAV RASTOGI": "{{ life_assured_name }}",
        "27/06/2026": "{{ allocation_date }}",
        "30/06/2026 10:58 AM": "{{ date_of_visit }}",
        "9897224624": "{{ contact_number }}",
        "201002": "{{ pin_code }}",
    },
    "LMS.docx": {
        "Virtual Investigation Services": "{{ agency_name }}",
    },
    "Kotak Life.docx": {
        "Virtual Investigation Services": "{{ agency_name }}",
        "Satyapal": "{{ field_investigator_name }}",
        "9161022060": "{{ fi_contact_number }}",
        "22.07.2026": "{{ assignment_date }}",
        "18.08.2026": "{{ report_submission_date }}",
        "27 days": "{{ tat_days }}",
        "80364896": "{{ policy_number }}",
        "22.06.2026": "{{ rcd }}",
        "1183306": "{{ sum_assured }}",
        "Ravi Kumar": "{{ life_assured_name }}",
        "02.09.2012": "{{ la_dob }}",
    },
    "Kotak Discreate Cheak.docx": {
        "Discreet Check_ KRN 1176871": "Discreet Check — KRN {{ krn_no }}",
        "24.08.2026": "{{ report_submission_date }}",
        "Pawan Garg": "{{ life_assured_name }}",
        "C/O SANJAY GARG, -10/48 RAJ NAGAR GHAZIABAD UTTAR PRADESH Pin code: 201002":
            "{{ la_address }}",
    },
    "PNB METLIFE.docx": {
        "463610627": "{{ application_number }}",
        "Virtual Investigation Services": "{{ agency_name }}",
        "Amit yadav": "{{ field_investigator_name }}",
        "13-08-2026": "{{ assignment_date }}",
        "26-08-2026": "{{ report_submission_date }}",
        "Kamlesh Agnihotri": "{{ life_assured_name }}",
        "9927034917": "{{ contact_number }}",
        "Rakesh Kumar Agnihotri 747 11 Kali charan marg Bagga colony Subhash "
        "nagar Bareilly Uttar Pradesh 243001 City Bareilly State Uttar Pradesh "
        "Pin Code 243001": "{{ la_address }}",
    },
    "Bajaj death claim.docx": {
        "0602836116": "{{ policy_number }}",
        "Bablu Khan": "{{ life_assured_name }}",
        "Sherwani": "{{ claimant_name }}",
        "2004-03-13 22 Years": "{{ la_dob }} {{ la_age }}",
        "13.03.2004": "{{ la_dob }}",
        "04.10.2024": "{{ date_of_death }}",
        "25.08.2024": "{{ rcd }}",
        "28.05.2026": "{{ assignment_date }}",
        "13.07.2026": "{{ report_submission_date }}",
        "5000000 /-": "{{ sum_assured }}",
        "Cardiac arrest": "{{ cause_of_death }}",
        "Gautam Buddha Nagar, UP": "{{ place_of_death }}",
        "9675314595": "{{ claimant_contact }}",
        "Virtual Investigation Services": "{{ agency_name }}",
        "9161022060": "{{ agency_contact }}",
    },
    "HDFC Death Claim.docx": {
        "PP000182": "{{ policy_number }}",
        "Roop Ratan Sahu": "{{ life_assured_name }}",
        "Shweta Sahu": "{{ claimant_name }}",
        "10.05.1974": "{{ la_dob }}",
        "02.08.2025": "{{ date_of_death }}",
        "12.05.2025": "{{ rcd }}",
        "10.09.2025": "{{ assignment_date }}",
        "23.09.2025": "{{ report_submission_date }}",
        "Suicide": "{{ cause_of_death }}",
        "Indore, MP.": "{{ place_of_death }}",
        "8979871038": "{{ claimant_contact }}",
        "Virtual Investigation Services": "{{ agency_name }}",
        "Amitabh": "{{ field_investigator_name }}",
        "9161022060": "{{ agency_contact }}",
    },
    "ICICI Death Claim.docx": {
        " 1157414": " {{ krn_no }}",
        "   K4825830": "   {{ policy_number }}",
        "Amarjeet Ramrati Chaudhary": "{{ life_assured_name }}",
        "3000000": "{{ sum_assured }}",
        "Madhu": "{{ claimant_name }}",
        "25.03.2025": "{{ rcd }}",
        "ICICI Pru GIFT Select": "{{ product_name }}",
        "VirtualOO7 Investigation Pvt. Ltd.": "{{ agency_name }}",
        "9161022060": "{{ agency_contact }}",
        "Shailendra": "{{ field_investigator_name }}",
        "9795290428": "{{ fi_contact_number }}",
        "15.06.2026": "{{ allocation_date }}",
        "26.06.2026": "{{ report_submission_date }}",
        "28.05.1980": "{{ la_dob }}",
        "45 years": "{{ la_age }}",
    },
    "FTI Icici.docx": {
        "1175072": "{{ krn_no }}",
        "K9590648": "{{ policy_number }}",
        "Kamla Tiwari": "{{ life_assured_name }}",
        "280019/-": "{{ sum_assured }}",
        "Varun Kumar Tiwari": "{{ claimant_name }}",
        "09.04.2026": "{{ rcd }}",
        "VirtualOO7 Investigation Private Limited": "{{ agency_name }}",
        "9161022060": "{{ agency_contact }}",
        "Shailendra": "{{ field_investigator_name }}",
        "8979382091": "{{ fi_contact_number }}",
        "03.08.2026": "{{ allocation_date }}",
        "10.04.2026": "{{ date_of_death }}",
        "BHU, Hospital": "{{ place_of_death }}",
        "Cardiac arrest": "{{ cause_of_death }}",
    },
    "SUD Life.docx": {
        "VirtualOO7 Investigation Pvt Ltd.": "{{ agency_name }}",
        "26.08.2026": "{{ report_submission_date }}",
        "Anand": "{{ field_investigator_name }}",
        "Mohan Kumar sahu": "{{ life_assured_name }}",
        "70534807": "{{ policy_number }}",
        "9709189309": "{{ contact_number }}",
        "02 Lacs/-": "{{ sum_assured }}",
        "anita devi": "{{ nominee_name }}",
        "Tamar Ranchi Jharkhand 835225.": "{{ la_address }}",
        "Kapil Sharma": "{{ report_prepared_by }}",
        "25.08.2026": "{{ date_of_visit }}",
    },
    "Land lord death claim.docx": {
        "Mr. Rakesh Kumar Singh": "{{ life_assured_name }}",
        "Agrasen Chauraha, Rama Complex, Civil Lines, Azamgarh Uttar Pradesh "
        "PIN 276001": "{{ la_address }}",
        "9411844780": "{{ contact_number }}",
        "8077357398": "{{ alternate_contact }}",
        "VirtualOO7 Investigation Pvt. Ltd.": "{{ agency_name }}",
        "Bhimsen": "{{ field_investigator_name }}",
        "9161022060": "{{ agency_contact }}",
        "26.05.2026": "{{ report_submission_date }}",
    },
}


async def run(dry_run: bool, only_file: str | None) -> int:
    settings.ensure_storage_dirs()
    total_reports = 0
    total_substitutions = 0
    lines: list[str] = []

    async with session_scope() as session:
        templates = (
            await session.execute(select(DocumentTemplate))
        ).scalars().all()
        by_filename = {template.original_filename: template for template in templates}

        for filename, replacements in REPLACEMENTS.items():
            if only_file and only_file.lower() not in filename.lower():
                continue

            template = by_filename.get(filename)
            source: Path | None = None
            if template is not None:
                candidate = settings.STORAGE_DIR / template.original_path
                if candidate.exists():
                    source = candidate
            if source is None:
                for folder in ("investigation_docs", "death_claim_docs"):
                    candidate = PROJECT_ROOT / folder / filename
                    if candidate.exists():
                        source = candidate
                        break
            if source is None:
                lines.append(f"  ! source not found: {filename}")
                continue

            if not docx_renderer.is_ooxml(source):
                lines.append(
                    f"  ! {filename}: legacy binary .doc — cannot be tagged. "
                    "Re-save as .docx first."
                )
                continue

            destination = settings.template_tagged_dir / (
                template.original_path.rsplit("/", 1)[-1]
                if template is not None
                else filename
            )
            target = destination if not dry_run else Path(
                settings.STORAGE_DIR / "_dryrun" / filename
            )
            report = tag_document(source, target, replacements, label=filename)
            lines.extend(report.as_lines())
            total_reports += 1
            total_substitutions += report.total

            if dry_run:
                target.unlink(missing_ok=True)
                continue

            if template is not None:
                found = docx_renderer.list_placeholders(destination)
                template.tagged_path = relative_to_storage(destination)
                template.placeholder_map = dict.fromkeys(found, "")
                if template.status == DocumentTemplateStatus.INACTIVE:
                    template.status = DocumentTemplateStatus.ACTIVE

    print("\n".join(lines))
    print("-" * 60)
    print(
        f"{total_reports} template(s) processed, "
        f"{total_substitutions} substitution(s)"
        + (" (dry run — nothing written)" if dry_run else "")
    )
    print(
        "\nNarrative paragraphs are intentionally left as-is. Open each tagged "
        "file in Word and replace the long remark blocks with "
        "{{ vicinity_remarks }}, {{ overall_remarks }} and {{ conclusion }}, then "
        "upload it as a new template version."
    )
    await dispose_engine()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only")
    parser.add_argument("--file", default=None, help="tag only this filename")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.dry_run, args.file)))
