"""Server-side pagination primitives.

Case lists can run to tens of thousands of rows, so every list endpoint paginates
in the database. Nothing bulk-loads into the frontend.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

MAX_PAGE_SIZE = 200


@dataclass(slots=True)
class PageParams:
    page: int = 1
    page_size: int = 25
    sort_by: str | None = None
    sort_dir: str = "desc"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir)


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class Page[T](BaseModel):
    items: list[T] = Field(default_factory=list)
    meta: PageMeta

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> Page[T]:
        total_pages = ceil(total / params.page_size) if params.page_size else 0
        return cls(
            items=items,
            meta=PageMeta(
                page=params.page,
                page_size=params.page_size,
                total=total,
                total_pages=total_pages,
                has_next=params.page < total_pages,
                has_previous=params.page > 1,
            ),
        )


async def count_query(session: AsyncSession, statement: Select[Any]) -> int:
    """COUNT(*) over an arbitrary select, without its ORDER BY / LIMIT."""
    bare = statement.order_by(None).limit(None).offset(None)
    counted = select(func.count()).select_from(bare.subquery())
    result = await session.execute(counted)
    return int(result.scalar_one())


async def paginate(
    session: AsyncSession,
    statement: Select[Any],
    params: PageParams,
) -> tuple[list[Any], int]:
    """Return ``(rows, total)`` for the given statement."""
    total = await count_query(session, statement)
    result = await session.execute(statement.offset(params.offset).limit(params.page_size))
    return list(result.unique().scalars().all()), total
