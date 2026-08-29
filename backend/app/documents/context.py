"""Builds the render context handed to a client's Word template.

Placeholder names are the ones catalogued in ``docs/ATTACHMENT_ANALYSIS.md`` §5.
Anything a template asks for that we do not know renders as an empty string
rather than blowing up mid-generation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.case import Case
from app.models.form import CaseForm
from app.services.case_workflow import status_label
from app.utils.dates import format_date, format_datetime, utcnow


class SafeContext(dict):
    """A dict that renders unknown placeholders as an empty string."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - jinja hook
        return ""


def _money(value: Decimal | float | None) -> str:
    if value in (None, ""):
        return ""
    try:
        amount = Decimal(str(value))
    except Exception:  # noqa: BLE001
        return str(value)
    return f"{amount:,.2f}".rstrip("0").rstrip(".")


def build_context(
    case: Case,
    case_form: CaseForm | None,
    *,
    settings_map: dict[str, Any],
    form_values: dict[str, Any] | None = None,
    generated_by: str | None = None,
) -> SafeContext:
    company = case.company
    case_type = case.case_type
    death = case.death_claim

    tat_days = None
    if case.received_at and case.completed_at:
        tat_days = max(0, (case.completed_at - case.received_at).days)

    context = SafeContext(
        # --- agency / report header -------------------------------------
        agency_name=settings_map.get("agency_name") or settings_map.get("organization_name", ""),
        agency_code=settings_map.get("agency_code", ""),
        agency_contact=settings_map.get("agency_contact", ""),
        field_investigator_name=(case.assigned_to.full_name if case.assigned_to else ""),
        fi_contact_number=(case.assigned_to.phone if case.assigned_to else "") or "",
        report_prepared_by=case.report_prepared_by or generated_by or "",
        generated_by=generated_by or "",
        generated_on=format_datetime(utcnow()),
        # --- case identity ----------------------------------------------
        case_number=case.case_number,
        company_name=company.name if company else "",
        company_short_name=company.short_name if company else "",
        case_type_name=case_type.name if case_type else "",
        krn_no=case.krn_no or "",
        policy_number=case.policy_number or "",
        application_number=case.application_number or "",
        external_reference=case.external_reference or "",
        product_name=case.product_name or "",
        sum_assured=_money(case.sum_assured),
        premium_amount=_money(case.premium_amount),
        rcd=format_date(case.risk_commencement_date),
        # --- life assured -------------------------------------------------
        life_assured_name=case.life_assured_name,
        la_address=case.address or "",
        la_dob=format_date(death.la_date_of_birth) if death else "",
        la_age=(death.la_age if death else "") or "",
        la_marital_status=(death.la_marital_status if death else "") or "",
        la_qualification=(death.la_qualification if death else "") or "",
        la_occupation=(death.la_occupation if death else "") or "",
        la_annual_income=(death.la_annual_income if death else "") or "",
        city=case.city or "",
        state=case.state or "",
        pin_code=case.pin_code or "",
        contact_number=case.contact_number or "",
        alternate_contact=case.alternate_contact or "",
        email_id=case.email_id or "",
        nominee_name=case.nominee_name or "",
        nominee_relation=case.nominee_relation or "",
        # --- claim ---------------------------------------------------------
        claimant_name=(death.claimant_name if death else "") or "",
        claimant_relation=(death.claimant_relation if death else "") or "",
        claimant_age=(death.claimant_age if death else "") or "",
        claimant_contact=(death.claimant_contact if death else "") or "",
        claimant_address=(death.claimant_address if death else "") or "",
        date_of_death=format_date(death.date_of_death) if death else "",
        place_of_death=(death.place_of_death if death else "") or "",
        cause_of_death=(death.cause_of_death if death else "") or "",
        type_of_death=(death.type_of_death if death else "") or "",
        standard_of_living=(death.standard_of_living if death else "") or "",
        # --- workflow dates -------------------------------------------------
        assignment_date=format_date(case.assigned_at or case.received_at),
        case_entrusted_date=format_date(case.received_at),
        allocation_date=format_date(case.received_at),
        received_date=format_date(case.received_at),
        date_of_visit=format_date(case.started_at),
        report_submission_date=format_date(case.submitted_at or case.report_date),
        completion_date=format_date(case.completed_at or case.completion_date),
        due_date=format_date(case.due_at),
        tat_days=f"{tat_days} days" if tat_days is not None else "",
        # --- outcome ---------------------------------------------------------
        outcome=case.outcome.value.title() if case.outcome else "",
        report_status=case.report_status.value.title() if case.report_status else "",
        status=status_label(case.status),
        outcome_reason=case.outcome_reason or "",
    )

    # Key-sensing checklist from the ICICI / Bajaj claim forms.
    if death is not None:
        context.update(
            profile_mismatch=death.profile_mismatch or "",
            medical_non_disclosure=death.medical_non_disclosure or "",
            death_before_issuance=death.death_before_issuance or "",
            impersonation=death.impersonation or "",
            forged_documents=death.forged_documents or "",
            nexus_involvement=death.nexus_involvement or "",
            industry_shopping=death.industry_shopping or "",
            other_adverse_findings=death.other_adverse_findings or "",
            no_adverse_findings=death.no_adverse_findings or "",
            rti_applied="Yes"
            if death.rti_applied
            else ("No" if death.rti_applied is False else ""),
            rti_status=death.rti_status or "",
            death_certificate_remarks=death.death_certificate_remarks or "",
        )

    # Dynamic form answers override / extend the header data.
    if form_values:
        for key, value in form_values.items():
            if value is None:
                continue
            if isinstance(value, list):
                context[key] = value
            else:
                context[key] = value

    # Row collections used by the repeating tables in every client form.
    for collection in (
        "family_members",
        "neighbours",
        "hospitals",
        "documents_collected",
        "other_policies",
        "vicinity_persons",
    ):
        context.setdefault(collection, context.get(collection) or [])

    return context
