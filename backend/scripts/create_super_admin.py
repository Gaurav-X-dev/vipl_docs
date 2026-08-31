"""Create — or repair — a Super Admin account from the command line.

There are two moments this is needed: the first sign-in after a deployment,
and the day somebody is locked out of a live system. Both want the same thing,
so this script does not distinguish between "create" and "reset". Give it an
email and a password:

    python -m scripts.create_super_admin --email you@example.com --password 'S3cret!'

If no account has that email, one is created with the Super Admin role and a
matching employee profile. If one already exists, its password is set, its
flags are put back to a state that can sign in, and any lockout from failed
attempts is cleared. Nothing else in the database is touched.

Add ``--name "Full Name"`` to set the display name, and ``--must-change`` to
force a password change at the next sign-in.

Unlike ``seed.py`` this takes the password from the argument rather than the
environment, so a live password never has to be written into ``.env``.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.permissions import SUPER_ADMIN_ROLE_CODE  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.models.enums import StaffCategory  # noqa: E402
from app.models.hr import Employee  # noqa: E402
from app.models.rbac import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.utils.dates import utcnow  # noqa: E402

MIN_PASSWORD_LENGTH = 10


async def next_employee_code(session: AsyncSession) -> str:
    """The next free EMPnnnn, read from what is already there.

    Codes are free text in the schema, so anything that does not look like
    EMPnnnn is ignored rather than allowed to break the count.
    """
    codes = (await session.execute(select(Employee.employee_code))).scalars().all()
    numbers = [
        int(match.group(1))
        for code in codes
        if (match := re.fullmatch(r"EMP(\d+)", (code or "").strip().upper()))
    ]
    return f"EMP{max(numbers, default=0) + 1:04d}"


async def attach_super_admin_role(session: AsyncSession, user: User) -> bool:
    """Give the user the Super Admin role. Returns whether it had to be added.

    The permission checks read the role, and ``is_super_admin`` alone does not
    grant one, so an account without it can sign in and then find half the
    application missing.
    """
    role = (
        await session.execute(select(Role).where(Role.code == SUPER_ADMIN_ROLE_CODE))
    ).scalar_one_or_none()
    if role is None:
        print(
            f"  ! The {SUPER_ADMIN_ROLE_CODE} role is missing — run scripts/seed.py.\n"
            "    The account is still usable, but its permissions will be thin."
        )
        return False
    if role.code in user.role_codes:
        return False
    user.roles = list(user.roles) + [role]
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or repair a Super Admin account.",
    )
    parser.add_argument("--email", required=True, help="Sign-in address.")
    parser.add_argument("--password", required=True, help="New password.")
    parser.add_argument("--name", default="", help='Display name, e.g. "Gaurav Pal".')
    parser.add_argument(
        "--must-change",
        action="store_true",
        help="Force a password change at the next sign-in.",
    )
    parser.add_argument(
        "--no-employee",
        action="store_true",
        help="Skip the employee profile (the account works without one).",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    if "@" not in email:
        print(f"'{args.email}' is not an email address.")
        return 2
    if len(args.password) < MIN_PASSWORD_LENGTH:
        print(f"The password must be at least {MIN_PASSWORD_LENGTH} characters.")
        return 2

    try:
        async with session_scope() as session:
            existing = (
                await session.execute(
                    select(User)
                    .options(selectinload(User.roles))
                    .where(func.lower(User.email) == email)
                )
            ).unique().scalar_one_or_none()

            name = args.name.strip()
            created = existing is None

            if existing is None:
                user = User(
                    email=email,
                    full_name=name or "Super Administrator",
                    staff_category=StaffCategory.MANAGEMENT,
                    # Set explicitly: on a new object this collection is
                    # unloaded, and reading it later would try to lazy-load
                    # inside async code, which raises MissingGreenlet.
                    roles=[],
                )
                session.add(user)
            else:
                user = existing
                if name:
                    user.full_name = name

            # Everything below applies to both paths: a repair has to undo
            # whatever state locked the account out in the first place.
            user.password_hash = hash_password(args.password)
            user.password_changed_at = utcnow()
            user.must_change_password = args.must_change
            user.is_super_admin = True
            user.is_active = True
            user.login_enabled = True
            user.failed_login_count = 0
            user.locked_until = None

            await session.flush()
            role_added = await attach_super_admin_role(session, user)

            employee_code = None
            if not args.no_employee:
                linked = (
                    await session.execute(
                        select(Employee).where(Employee.user_id == user.id)
                    )
                ).scalar_one_or_none()
                if linked is None:
                    parts = (name or "Super Administrator").split(" ")
                    employee_code = await next_employee_code(session)
                    session.add(
                        Employee(
                            employee_code=employee_code,
                            user_id=user.id,
                            first_name=parts[0],
                            last_name=" ".join(parts[1:]) or None,
                            email=email,
                            staff_category=StaffCategory.MANAGEMENT,
                            joining_date=utcnow().date(),
                        )
                    )
                else:
                    employee_code = linked.employee_code

            print("Super Admin account created." if created else "Super Admin account updated.")
            print(f"  email    : {email}")
            print(f"  password : {args.password}")
            print(f"  name     : {user.full_name}")
            if employee_code:
                print(f"  employee : {employee_code}")
            if role_added:
                print(f"  role     : {SUPER_ADMIN_ROLE_CODE} attached")
            if args.must_change:
                print("  A password change is required at the next sign-in.")
            if not created:
                print("\nThe previous password no longer works.")
            return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
