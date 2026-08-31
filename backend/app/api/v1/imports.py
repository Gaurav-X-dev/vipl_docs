"""Excel / CSV import endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import DbSession, require_permissions
from app.core.pagination import Page, PageParams, page_params, paginate
from app.imports.mapping import CANONICAL_FIELDS, FIELD_LABELS
from app.models.enums import (
    ActivityAction,
    CaseCategory,
    CasePriority,
    ImportRowStatus,
)
from app.models.importing import ImportBatch, ImportTemplate
from app.models.user import User
from app.schemas.common import Message
from app.schemas.misc import (
    ImportBatchOut,
    ImportCommitOut,
    ImportCommitRequest,
    ImportPreviewOut,
    ImportPreviewRow,
    ImportSummary,
    ImportTemplateOut,
)
from app.services import activity_service, export_service, import_service

router = APIRouter(prefix="/imports", tags=["Import"])

ImportUser = Annotated[User, Depends(require_permissions("import.create"))]
ViewImports = Annotated[User, Depends(require_permissions("import.view"))]
RollbackUser = Annotated[User, Depends(require_permissions("import.rollback"))]
PageDep = Annotated[PageParams, Depends(page_params)]

PREVIEW_ROWS = 50


@router.get("/fields")
async def available_fields(user: ViewImports) -> list[dict[str, str]]:
    """The internal fields a spreadsheet column can be mapped onto."""
    return [{"value": name, "label": FIELD_LABELS.get(name, name)} for name in CANONICAL_FIELDS]


@router.get("/templates", response_model=list[ImportTemplateOut])
async def list_templates(session: DbSession, user: ViewImports) -> list[ImportTemplateOut]:
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(ImportTemplate)
        .options(
            selectinload(ImportTemplate.mappings),
            selectinload(ImportTemplate.company),
        )
        .order_by(ImportTemplate.is_default.desc(), ImportTemplate.name)
    )
    templates = result.unique().scalars().all()
    return [
        ImportTemplateOut(
            **{
                **{
                    key: getattr(template, key)
                    for key in (
                        "id",
                        "code",
                        "name",
                        "description",
                        "company_id",
                        "header_row",
                        "sheet_name",
                        "duplicate_key_fields",
                        "fallback_duplicate_key_fields",
                        "is_default",
                        "is_active",
                    )
                },
                "company_name": template.company.short_name if template.company else None,
                "mappings": template.mappings,
            }
        )
        for template in templates
    ]


@router.get("", response_model=Page[ImportBatchOut])
async def list_batches(
    session: DbSession, user: ViewImports, params: PageDep
) -> Page[ImportBatchOut]:
    from sqlalchemy.orm import selectinload

    statement = (
        select(ImportBatch)
        .options(
            selectinload(ImportBatch.template),
            selectinload(ImportBatch.company),
            selectinload(ImportBatch.uploaded_by),
        )
        .order_by(ImportBatch.created_at.desc())
    )
    rows, total = await paginate(session, statement, params)
    items = [ImportBatchOut(**import_service.batch_payload(batch)) for batch in rows]
    return Page.build(items, total, params)


@router.post("/upload", response_model=ImportPreviewOut, status_code=201)
async def upload(
    request: Request,
    session: DbSession,
    user: ImportUser,
    file: Annotated[UploadFile, File(description=".xlsx, .xlsm or .csv")],
    template_id: Annotated[uuid.UUID | None, Form()] = None,
    company_id: Annotated[uuid.UUID | None, Form()] = None,
    category: Annotated[CaseCategory | None, Form()] = None,
) -> ImportPreviewOut:
    """Upload, parse and validate — nothing is created until you confirm.

    ``category`` is the queue the file was dropped into. Death claim and
    investigation sheets arrive from different desks in different formats, so
    each screen imports only its own kind and a row from the other queue is
    reported rather than quietly filed in the wrong place.
    """
    payload = await file.read()
    batch, mapping, sheet = await import_service.upload_and_validate(
        session,
        filename=file.filename or "import.xlsx",
        payload=payload,
        template_id=template_id,
        company_id=company_id,
        actor=user,
        category=category,
        request=request,
    )
    await session.commit()
    # Reload with all relationships used by ``batch_payload`` eagerly loaded;
    # implicit relationship I/O is not available in an AsyncSession.
    batch = await import_service.get_batch(session, batch.id)
    return await _preview_payload(session, batch, limit=PREVIEW_ROWS)


@router.get("/{batch_id}", response_model=ImportBatchOut)
async def get_batch(batch_id: uuid.UUID, session: DbSession, user: ViewImports) -> ImportBatchOut:
    batch = await import_service.get_batch(session, batch_id)
    return ImportBatchOut(**import_service.batch_payload(batch))


@router.get("/{batch_id}/preview", response_model=ImportPreviewOut)
async def preview(
    batch_id: uuid.UUID,
    session: DbSession,
    user: ViewImports,
    limit: int = Query(PREVIEW_ROWS, ge=1, le=500),
    row_status: ImportRowStatus | None = Query(None),
) -> ImportPreviewOut:
    batch = await import_service.get_batch(session, batch_id)
    return await _preview_payload(
        session, batch, limit=limit, statuses=[row_status] if row_status else None
    )


async def _preview_payload(
    session,
    batch: ImportBatch,
    *,
    limit: int,
    statuses: list[ImportRowStatus] | None = None,
) -> ImportPreviewOut:
    rows = await import_service.get_rows(session, batch.id, statuses=statuses, limit=limit)
    applied = batch.applied_mapping or {}
    headers = batch.detected_headers or []
    return ImportPreviewOut(
        batch=ImportBatchOut(**import_service.batch_payload(batch)),
        summary=ImportSummary(
            total_rows=batch.total_rows,
            valid=batch.valid_rows,
            warnings=batch.warning_rows,
            errors=batch.error_rows,
            duplicates=batch.duplicate_rows,
            imported=batch.imported_rows,
        ),
        headers=headers,
        mapping=applied,
        unmapped_headers=[h for h in headers if not applied.get(h)],
        missing_required=[],
        rows=[
            ImportPreviewRow(
                row_number=row.row_number,
                raw=row.raw_data or {},
                parsed=row.parsed_data or {},
                status=row.status,
                errors=row.errors or [],
                warnings=row.warnings or [],
                duplicate_of=str(row.duplicate_of_case_id) if row.duplicate_of_case_id else None,
            )
            for row in rows
        ],
    )


@router.post("/{batch_id}/commit", response_model=ImportCommitOut)
async def commit(
    batch_id: uuid.UUID,
    payload: ImportCommitRequest,
    request: Request,
    session: DbSession,
    user: ImportUser,
) -> ImportCommitOut:
    """Create the cases. Runs in one transaction — all or nothing."""
    priority = CasePriority.NORMAL
    if payload.default_priority:
        try:
            priority = CasePriority(payload.default_priority.upper())
        except ValueError:
            priority = CasePriority.NORMAL

    batch, created_ids = await import_service.commit_batch(
        session,
        batch_id,
        actor=user,
        skip_duplicates=payload.skip_duplicates,
        auto_assign=payload.auto_assign,
        apply_file_status=payload.apply_file_status,
        default_priority=priority,
        request=request,
    )
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.IMPORT_RUN,
        summary=(f"Imported {len(created_ids)} case(s) from {batch.original_filename}"),
        detail=f"Batch {batch.batch_number}",
        entity_type="ImportBatch",
        entity_id=batch.id,
        entity_label=batch.batch_number,
        request=request,
    )
    await session.commit()
    batch = await import_service.get_batch(session, batch.id)
    return ImportCommitOut(
        batch=ImportBatchOut(**import_service.batch_payload(batch)),
        summary=ImportSummary(
            total_rows=batch.total_rows,
            valid=batch.valid_rows,
            warnings=batch.warning_rows,
            errors=batch.error_rows,
            duplicates=batch.duplicate_rows,
            imported=batch.imported_rows,
        ),
        created_case_ids=created_ids,
        message=(f"{batch.imported_rows} case(s) created from {batch.original_filename}."),
    )


@router.post("/{batch_id}/rollback", response_model=Message)
async def rollback(
    batch_id: uuid.UUID,
    request: Request,
    session: DbSession,
    user: RollbackUser,
) -> Message:
    batch = await import_service.rollback_batch(session, batch_id, actor=user, request=request)
    await session.commit()
    return Message(
        message=f"Batch {batch.batch_number} rolled back.",
        detail="All cases created by this import were deleted.",
    )


@router.get("/{batch_id}/errors/download")
async def download_errors(batch_id: uuid.UUID, session: DbSession, user: ViewImports) -> Response:
    """Rejected-rows workbook: row number, original data, error message."""
    batch = await import_service.get_batch(session, batch_id)
    rows = await import_service.get_rows(
        session,
        batch.id,
        statuses=[ImportRowStatus.ERROR, ImportRowStatus.DUPLICATE],
    )
    payload = export_service.import_error_workbook(rows, batch.detected_headers or [])
    name = f"{batch.batch_number}_rejected_rows.xlsx"
    return Response(
        content=payload,
        media_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
