from __future__ import annotations
from typing import Any, Literal
from pydantic import Field
import uuid
from beanie import Document as BeanieDocument


class Document(BeanieDocument):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    project_id: str
    template_id: str | None = None
    name: str
    type: Literal["tz", "tp", "rp", "other"] | None = None
    status: Literal["draft", "pending", "approved", "revision", "rejected"] = "draft"
    locked: bool = False  # set by Kafka consumer on workflow events

    function_ids: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=lambda: {"sections": {}})

    version: int = 1
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    class Settings:
        name = "documents"
