"""Shared schema building blocks."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Message(BaseModel):
    message: str
    detail: str | None = None


class IdResponse(BaseModel):
    id: uuid.UUID
    message: str = "Saved."


class LookupOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str


class UserBrief(ORMModel):
    """The compact user shape embedded in lists and detail payloads."""

    id: uuid.UUID
    full_name: str
    email: str
    staff_category: str | None = None
    is_online: bool = False
    last_activity_at: datetime | None = None


class OptionOut(BaseModel):
    value: str
    label: str


class CountByLabel(BaseModel):
    label: str
    value: int
    percent: float = 0.0
    extra: dict[str, Any] = Field(default_factory=dict)


class HealthOut(BaseModel):
    status: str
    app: str
    environment: str
    version: str
    timezone: str
    server_time: datetime
    database: str
