from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel


class TemplateCreate(BaseModel):
    type: Literal["tz", "chtz", "pmi", "nmck"]
    name: str
    gost_ref: str = ""
    output_format: Literal["docx", "xlsx"] = "docx"
    project_id: str | None = None
    parent_id: str | None = None
    dotx_file_key: str = ""
    formatting: dict[str, Any] = {}
    sections: list[dict[str, Any]] = []


class TemplateUpdate(BaseModel):
    name: str | None = None
    gost_ref: str | None = None
    dotx_file_key: str | None = None
    formatting: dict[str, Any] | None = None
    sections: list[dict[str, Any]] | None = None


class TemplateResponse(BaseModel):
    id: str
    type: str
    name: str
    gost_ref: str
    output_format: str
    is_system: bool
    parent_id: str | None
    project_id: str | None
    dotx_file_key: str
    formatting: dict[str, Any]
    sections: list[dict[str, Any]]
    version: int
    created_by: str
    created_at: str
    updated_at: str
