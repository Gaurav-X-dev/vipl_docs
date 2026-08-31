"""Check that a deployment is actually ready to be used.

Every problem this project has hit on the server was silent at deploy time and
loud later, in front of the client: templates that were seeded but never
tagged, so the DOCX button failed on the first real case; a storage directory
owned by root while the service runs as nobody; a database at the wrong
migration. None of these show up in ``systemctl status``, which happily
reports a healthy process serving a broken application.

So this is the last step of a deploy, and the first thing to run when
something is wrong::

    python -m scripts.doctor

Each check prints ``ok``, ``warn`` or ``FAIL``, and every failure carries the
command that fixes it. The exit code is non-zero if anything failed, so it can
gate a deployment script.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select, text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.models.company import CaseType, Company  # noqa: E402
from app.models.document import DocumentTemplate  # noqa: E402
from app.models.enums import DocumentTemplateStatus  # noqa: E402
from app.models.form import FormTemplate  # noqa: E402
from app.models.user import User  # noqa: E402
from app.utils.files import resolve_storage_path  # noqa: E402

OK, WARN, FAIL = "ok", "warn", "FAIL"


@dataclass
class Report:
    rows: list[tuple[str, str, str, str | None]] = field(default_factory=list)

    def add(self, level: str, name: str, detail: str, fix: str | None = None) -> None:
        self.rows.append((level, name, detail, fix))

    @property
    def failed(self) -> int:
        return sum(1 for level, *_ in self.rows if level == FAIL)

    @property
    def warned(self) -> int:
        return sum(1 for level, *_ in self.rows if level == WARN)

    def render(self) -> None:
        width = max(len(name) for _, name, _, _ in self.rows)
        print()
        for level, name, detail, fix in self.rows:
            print(f"  [{level:>4}]  {name:<{width}}  {detail}")
            if fix and level != OK:
                print(f"          {'':<{width}}  -> {fix}")
        print()


async def check_database(report: Report) -> None:
    async with session_scope() as session:
        try:
            await session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - the message is the point
            report.add(FAIL, "database", f"cannot connect: {exc}", "check DATABASE_URL in .env")
            return

        dialect = session.bind.dialect.name
        report.add(OK, "database", f"connected ({dialect})")
        if dialect == "sqlite" and settings.APP_ENV == "production":
            report.add(
                WARN,
                "database engine",
                "production is running on SQLite",
                "use PostgreSQL for a live installation",
            )

        version = (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one_or_none()
        if version:
            report.add(OK, "migrations", f"at {version}")
        else:
            report.add(
                FAIL,
                "migrations",
                "no alembic_version row",
                ".venv/bin/python -m alembic upgrade head",
            )

        companies = (await session.execute(select(func.count()).select_from(Company))).scalar_one()
        case_types = (
            await session.execute(select(func.count()).select_from(CaseType))
        ).scalar_one()
        forms = (
            await session.execute(select(func.count()).select_from(FormTemplate))
        ).scalar_one()
        if companies and case_types and forms:
            report.add(
                OK,
                "seed data",
                f"{companies} companies, {case_types} case types, {forms} forms",
            )
        else:
            report.add(
                FAIL,
                "seed data",
                f"{companies} companies, {case_types} case types, {forms} forms",
                ".venv/bin/python scripts/seed.py",
            )

        await check_templates(session, report)
        await check_super_admin(session, report)


async def check_templates(session, report: Report) -> None:
    """The failure that reached a client: seeded, but never tagged."""
    rows = (await session.execute(select(DocumentTemplate))).scalars().all()
    if not rows:
        report.add(
            FAIL,
            "document templates",
            "none registered",
            ".venv/bin/python scripts/seed.py",
        )
        return

    untagged = [
        row
        for row in rows
        if row.status == DocumentTemplateStatus.ACTIVE and not row.tagged_path
    ]
    legacy = [row for row in rows if row.status == DocumentTemplateStatus.NEEDS_CONVERSION]
    ready = [row for row in rows if row.status == DocumentTemplateStatus.ACTIVE and row.tagged_path]

    if untagged:
        report.add(
            FAIL,
            "tagged templates",
            f"{len(untagged)} of {len(rows)} have no tagged copy: "
            + ", ".join(t.name for t in untagged[:3])
            + ("…" if len(untagged) > 3 else ""),
            "python -m scripts.tag_templates && python -m scripts.retag_templates --confirm",
        )
    else:
        report.add(OK, "tagged templates", f"{len(ready)} ready to generate DOCX")

    if legacy:
        report.add(
            WARN,
            "legacy .doc files",
            f"{len(legacy)} cannot generate DOCX: " + ", ".join(t.name for t in legacy),
            "re-save each as .docx and upload it as a new version (PDF still works)",
        )

    # A tagged_path in the database that is not on disk fails at download time,
    # which is the worst moment to find out.
    missing = [
        row
        for row in ready
        if not resolve_storage_path(row.tagged_path).exists()
    ]
    if missing:
        report.add(
            FAIL,
            "template files",
            f"{len(missing)} tagged file(s) recorded but not on disk",
            "python -m scripts.tag_templates",
        )
    else:
        report.add(OK, "template files", "all tagged files present on disk")


async def check_super_admin(session, report: Report) -> None:
    admins = (
        await session.execute(
            select(func.count()).select_from(User).where(User.is_super_admin.is_(True))
        )
    ).scalar_one()
    if admins:
        report.add(OK, "super admin", f"{admins} account(s)")
    else:
        report.add(
            FAIL,
            "super admin",
            "nobody can sign in",
            "python -m scripts.create_super_admin --email you@example.com --password '...'",
        )


def check_storage(report: Report) -> None:
    directories = {
        "storage root": settings.STORAGE_DIR,
        "imports": settings.import_files_dir,
        "case documents": settings.case_documents_dir,
        "generated documents": settings.generated_documents_dir,
        "template originals": settings.template_originals_dir,
        "template tagged": settings.template_tagged_dir,
    }
    for name, directory in directories.items():
        path = Path(directory)
        if not path.exists():
            report.add(FAIL, name, f"missing: {path}", f"mkdir -p {path}")
            continue
        # Writability is what actually matters: the service runs as its own
        # user, and a directory created by root during deployment is readable
        # but not writable by it.
        probe = path / ".doctor-write-test"
        try:
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            report.add(
                FAIL,
                name,
                f"not writable by {_whoami()}: {exc.strerror or exc}",
                f"chown -R <service-user> {settings.STORAGE_DIR}",
            )
        else:
            report.add(OK, name, str(path))


def check_configuration(report: Report) -> None:
    if settings.APP_ENV == "production":
        report.add(OK, "environment", "production")
        if settings.DEBUG:
            report.add(FAIL, "debug", "DEBUG is on in production", "set DEBUG=false in .env")
        else:
            report.add(OK, "debug", "off")
        if len(settings.SECRET_KEY) < 32:
            report.add(
                FAIL,
                "secret key",
                "too short to be a generated key",
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\"",
            )
        else:
            report.add(OK, "secret key", "set")
        origins = [o for o in settings.CORS_ORIGINS if o]
        if not origins or any("localhost" in o for o in origins):
            report.add(
                WARN,
                "CORS origins",
                ", ".join(origins) or "(none)",
                "set CORS_ORIGINS to the live domain only",
            )
        else:
            report.add(OK, "CORS origins", ", ".join(origins))
    else:
        report.add(WARN, "environment", settings.APP_ENV, "set APP_ENV=production on the server")

    report.add(OK, "retention", f"{settings.DATA_RETENTION_DAYS} days")


def _whoami() -> str:
    try:
        return os.getlogin()
    except OSError:
        return f"uid {getattr(os, 'geteuid', lambda: '?')()}"


async def main() -> int:
    report = Report()
    print(f"Checking {settings.APP_NAME} ({settings.APP_ENV})")
    try:
        check_configuration(report)
        check_storage(report)
        await check_database(report)
    finally:
        await dispose_engine()

    report.render()
    if report.failed:
        print(f"{report.failed} check(s) failed. The application will not work correctly.")
        return 1
    if report.warned:
        print(f"All checks passed, with {report.warned} warning(s).")
        return 0
    print("Everything checks out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
