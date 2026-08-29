"""Development-only demo data.

Creates a handful of staff accounts and demonstration cases so the dashboard,
assignment and workflow screens have something to show on a fresh install.

No real customer information is used — every name here is invented.
"""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.case import Case
from app.models.company import CaseType, Company
from app.models.enums import (
    CaseCategory,
    CaseOutcome,
    CasePriority,
    CaseStatus,
    EmploymentStatus,
    Gender,
    ReportStatus,
    StaffCategory,
)
from app.models.hr import Department, Designation, Employee
from app.models.rbac import Role
from app.models.user import User
from app.schemas.case import CaseCreate
from app.services import case_service, form_service
from app.utils.dates import utcnow

DEMO_PASSWORD = "Demo@123456"

DEMO_STAFF: tuple[tuple[str, str, str, str, StaffCategory, str, str], ...] = (
    (
        "EMP1001",
        "Rahul",
        "Sharma",
        "rahul.sharma@investigation.local",
        StaffCategory.FIELD,
        "INVESTIGATOR",
        "Lucknow",
    ),
    (
        "EMP1002",
        "Anita",
        "Verma",
        "anita.verma@investigation.local",
        StaffCategory.FIELD,
        "INVESTIGATOR",
        "Kanpur",
    ),
    (
        "EMP1003",
        "Imran",
        "Qureshi",
        "imran.qureshi@investigation.local",
        StaffCategory.FIELD,
        "INVESTIGATOR",
        "Noida",
    ),
    (
        "EMP1004",
        "Sneha",
        "Nair",
        "sneha.nair@investigation.local",
        StaffCategory.BACK_OFFICE,
        "DATA_ENTRY",
        "Lucknow",
    ),
    (
        "EMP1005",
        "Vikas",
        "Mehta",
        "vikas.mehta@investigation.local",
        StaffCategory.BACK_OFFICE,
        "REVIEWER",
        "Lucknow",
    ),
    (
        "EMP1006",
        "Priya",
        "Deshmukh",
        "priya.deshmukh@investigation.local",
        StaffCategory.MANAGEMENT,
        "MANAGER",
        "Lucknow",
    ),
    (
        "EMP1007",
        "Farhan",
        "Ali",
        "farhan.ali@investigation.local",
        StaffCategory.BACK_OFFICE,
        "HR",
        "Lucknow",
    ),
    (
        "EMP1008",
        "Priyanka",
        "Singh",
        "priyanka.singh@investigation.local",
        StaffCategory.BACK_OFFICE,
        "OFFICE_STAFF",
        "Lucknow",
    ),
    (
        "EMP1009",
        "Arjun",
        "Rao",
        "arjun.rao@investigation.local",
        StaffCategory.BACK_OFFICE,
        "OFFICE_STAFF",
        "Kanpur",
    ),
)

DEMO_CASES: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    # company, case type, life assured, city, state, policy, krn
    (
        "ICICI",
        "PRE_ISSUANCE",
        "Ramesh Chandra Yadav",
        "Lucknow",
        "Uttar Pradesh",
        "K9101234",
        "1180011",
    ),
    ("ICICI", "DISCREET_CHECK", "Sunita Devi", "Ghaziabad", "Uttar Pradesh", "K9101235", "1180012"),
    ("HDFC", "PROFILE_CHECK", "Mohammad Arif", "Meerut", "Uttar Pradesh", "PP000911", "1180013"),
    ("BAJAJ", "PRE_ISSUANCE", "Kavita Singh", "Kanpur", "Uttar Pradesh", "0602911001", "1180014"),
    ("KOTAK", "PRE_CLAIM", "Deepak Rathore", "Jodhpur", "Rajasthan", "80399100", "1180015"),
    ("HSBC", "PRE_ISSUANCE", "Harish Verma", "Mathura", "Uttar Pradesh", "9103990001", "1180016"),
    ("ABSLI", "PRE_ISSUANCE", "Farida Begum", "Lucknow", "Uttar Pradesh", "9928811", "1180017"),
    (
        "BANDHAN",
        "PRE_ISSUANCE",
        "Ankit Mishra",
        "Ayodhya",
        "Uttar Pradesh",
        "ALI000001099",
        "1180018",
    ),
    (
        "PNBMET",
        "PRE_CLAIM",
        "Shalini Agnihotri",
        "Bareilly",
        "Uttar Pradesh",
        "463610988",
        "1180019",
    ),
    ("BAXA", "PRE_CLAIM", "Zubair Ahmad", "Pilibhit", "Uttar Pradesh", "503-9838900", "1180020"),
    ("BAJAJ", "DEATH_CLAIM", "Suresh Prajapati", "Noida", "Uttar Pradesh", "0602911002", "1180021"),
    ("HDFC", "DEATH_CLAIM", "Rekha Sahu", "Indore", "Madhya Pradesh", "PP000912", "1180022"),
    ("ICICI", "DEATH_CLAIM", "Ganesh Chaudhary", "Thane", "Maharashtra", "K4825999", "1180023"),
    (
        "ICICI",
        "DEATH_CLAIM_FTI",
        "Kamla Tripathi",
        "Varanasi",
        "Uttar Pradesh",
        "K9590777",
        "1180024",
    ),
    ("SUD", "DEATH_CLAIM", "Mohan Sahu", "Ranchi", "Jharkhand", "70534900", "1180025"),
    (
        "ICICI",
        "PAYOUT_VERIFICATION",
        "Abhinav Rastogi",
        "Ghaziabad",
        "Uttar Pradesh",
        "19681299",
        "1180026",
    ),
)


async def seed_demo(session: AsyncSession) -> list[str]:
    """Create demo staff and cases. Returns lines for the seed report."""
    notes: list[str] = []

    existing_cases = int(
        (await session.execute(select(func.count()).select_from(Case))).scalar_one()
    )
    if existing_cases > 0:
        notes.append(f"\n  - demo skipped: the database already holds {existing_cases} case(s).")
        return notes

    roles = {row.code: row for row in (await session.execute(select(Role))).scalars().all()}
    departments = {
        row.code: row for row in (await session.execute(select(Department))).scalars().all()
    }
    designations = {
        row.code: row for row in (await session.execute(select(Designation))).scalars().all()
    }
    companies = {row.code: row for row in (await session.execute(select(Company))).scalars().all()}
    case_types = {
        row.code: row for row in (await session.execute(select(CaseType))).scalars().all()
    }

    admin = (
        (
            await session.execute(
                select(User).options(selectinload(User.roles)).where(User.is_super_admin.is_(True))
            )
        )
        .unique()
        .scalars()
        .first()
    )

    # --- staff ------------------------------------------------------------
    investigators: list[User] = []
    created_staff = 0
    for code, first, last, email, category, role_code, city in DEMO_STAFF:
        existing = (
            await session.execute(select(Employee).where(Employee.employee_code == code))
        ).scalar_one_or_none()
        if existing is not None:
            if existing.user is not None and category == StaffCategory.FIELD:
                investigators.append(existing.user)
            continue

        user = User(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name=f"{first} {last}",
            phone=f"9{random.randint(100000000, 999999999)}",
            staff_category=category,
            is_active=True,
            login_enabled=True,
            must_change_password=False,
            password_changed_at=utcnow(),
        )
        role = roles.get(role_code)
        if role is not None:
            user.roles = [role]
        session.add(user)
        await session.flush()

        department_code = (
            "OPS"
            if category == StaffCategory.FIELD
            else "HR"
            if role_code == "HR"
            else "QC"
            if role_code == "REVIEWER"
            else "BACKOFF"
        )
        designation_code = (
            "IO"
            if category == StaffCategory.FIELD
            else "HREXEC"
            if role_code == "HR"
            else "QCEXEC"
            if role_code == "REVIEWER"
            else "MGR"
            if role_code == "MANAGER"
            else "DEO"
        )
        session.add(
            Employee(
                employee_code=code,
                user_id=user.id,
                first_name=first,
                last_name=last,
                gender=Gender.UNDISCLOSED,
                email=email,
                mobile=user.phone,
                city=city,
                state="Uttar Pradesh",
                department_id=departments[department_code].id
                if department_code in departments
                else None,
                designation_id=designations[designation_code].id
                if designation_code in designations
                else None,
                staff_category=category,
                joining_date=(utcnow() - timedelta(days=random.randint(90, 900))).date(),
                employment_status=EmploymentStatus.ACTIVE,
                base_city=city,
                base_state="Uttar Pradesh",
            )
        )
        created_staff += 1
        if category == StaffCategory.FIELD:
            investigators.append(user)

    await session.flush()

    # A couple of investigators look "online" so the green/red indicator has
    # something to show immediately after seeding.
    for user in investigators[:2]:
        user.last_activity_at = utcnow()
        user.last_login_at = utcnow() - timedelta(minutes=20)

    # --- cases ------------------------------------------------------------
    created_cases = 0
    now = utcnow()
    for index, (company_code, type_code, name, city, state, policy, krn) in enumerate(DEMO_CASES):
        company = companies.get(company_code)
        case_type = case_types.get(type_code)
        if company is None or case_type is None:
            continue

        received = now - timedelta(days=random.randint(1, 40), hours=random.randint(0, 20))
        payload = CaseCreate(
            company_id=company.id,
            case_type_id=case_type.id,
            life_assured_name=name,
            policy_number=policy,
            krn_no=krn,
            city=city,
            state=state,
            pin_code=f"2{random.randint(10000, 99999)}",
            contact_number=f"9{random.randint(100000000, 999999999)}",
            address=f"House {random.randint(1, 250)}, {city}, {state}",
            received_at=received,
            priority=random.choice(list(CasePriority)),
        )
        case = await case_service.create_case(session, payload, actor=admin, attach_form=True)
        case.received_month = received.strftime("%b-%Y")

        # Spread the demo cases across the workflow so every dashboard tile
        # and every status filter has data behind it.
        stage = index % 6
        if stage == 0:
            case.status = CaseStatus.UNASSIGNED
        elif investigators:
            assignee = investigators[index % len(investigators)]
            await case_service.assign_case(
                session,
                case,
                assigned_to_id=assignee.id,
                actor=admin,
                notes="Demo assignment",
            )
            if stage == 2:
                case.status = CaseStatus.WIP
                case.started_at = received + timedelta(days=1)
            elif stage == 3:
                case.status = CaseStatus.RIP
                case.started_at = received + timedelta(days=1)
            elif stage == 4:
                case.status = CaseStatus.REPORT_SUBMITTED
                case.started_at = received + timedelta(days=1)
                case.submitted_at = received + timedelta(days=4)
                case.outcome = random.choice(list(CaseOutcome))
                case.report_status = ReportStatus.FINAL
            elif stage == 5:
                case.status = CaseStatus.COMPLETED
                case.started_at = received + timedelta(days=1)
                case.submitted_at = received + timedelta(days=4)
                case.verified_at = received + timedelta(days=5)
                case.completed_at = received + timedelta(days=5)
                case.completion_date = (received + timedelta(days=5)).date()
                case.outcome = random.choice(list(CaseOutcome))
                case.report_status = ReportStatus.FINAL
        created_cases += 1

    await session.flush()

    notes.append("")
    notes.append(f"Demo data: {created_staff} staff account(s), {created_cases} case(s).")
    notes.append(f"  Demo staff password: {DEMO_PASSWORD}")
    notes.append("  Example investigator login: rahul.sharma@investigation.local")
    notes.append("  Example office staff login:  priyanka.singh@investigation.local")
    return notes
