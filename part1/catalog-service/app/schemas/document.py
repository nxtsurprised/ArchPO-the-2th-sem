from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel


class DocumentCreate(BaseModel):
    project_id: str
    template_id: str
    name: str
    type: Literal["tz", "chtz", "pmi", "nmck"]
    function_ids: list[str] = []
    data: dict[str, Any] = {}


class DocumentUpdate(BaseModel):
    name: str | None = None
    function_ids: list[str] | None = None
    data: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    template_id: str
    name: str
    type: str
    status: str
    function_ids: list[str]
    data: dict[str, Any]
    version: int
    created_by: str
    created_at: str
    updated_at: str


class ValidationError(BaseModel):
    field: str
    message: str


class DocumentValidationResponse(BaseModel):
    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []
