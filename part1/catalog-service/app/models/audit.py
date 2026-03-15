from __future__ import annotations
from typing import Any
from pydantic import Field
import uuid
from beanie import Document


class AuditLog(Document):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    timestamp: str = ""
    user_id: str = "system"
    user_side: str | None = None
    user_role: str | None = None
    ip_address: str = "unknown"
    user_agent: str | None = None
    service: str = "catalog"
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    project_id: str | None = None
    correlation_id: str | None = None
    result: str = "success"
    changes: dict[str, Any] | None = None
    details: dict[str, Any] | None = None

    class Settings:
        name = "audit_log"
