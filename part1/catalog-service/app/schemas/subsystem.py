from __future__ import annotations
from pydantic import BaseModel


class SubsystemCreate(BaseModel):
    project_id: str
    code: str
    name: str
    description: str = ""
    order: int = 0
    tz_section_prefix: str = ""


class SubsystemUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    order: int | None = None
    tz_section_prefix: str | None = None


class SubsystemReorder(BaseModel):
    ids: list[str]


class SubsystemResponse(BaseModel):
    id: str
    project_id: str
    code: str
    name: str
    description: str
    order: int
    tz_section_prefix: str
    created_at: str
    updated_at: str
