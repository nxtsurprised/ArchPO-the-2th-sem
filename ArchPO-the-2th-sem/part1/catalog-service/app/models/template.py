from __future__ import annotations
from typing import Any, Literal
from pydantic import Field
import uuid
from beanie import Document


class Template(Document):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    type: Literal["tz", "chtz", "pmi", "nmck"]
    name: str
    gost_ref: str = ""
    output_format: Literal["docx", "xlsx"] = "docx"
    is_system: bool = False
    parent_id: str | None = None
    project_id: str | None = None
    dotx_file_key: str = ""

    formatting: dict[str, Any] = Field(default_factory=dict)
    sections: list[dict[str, Any]] = Field(default_factory=list)

    version: int = 1
    created_by: str = "system"
    created_at: str = ""
    updated_at: str = ""

    class Settings:
        name = "templates"
