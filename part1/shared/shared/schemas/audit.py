from __future__ import annotations
from uuid import UUID
from typing import Literal
from datetime import datetime
from pydantic import BaseModel


class AuditEntry(BaseModel):
    id: UUID
    timestamp: datetime
    user_id: UUID
    user_side: str | None
    user_role: str | None
    ip_address: str
    user_agent: str | None
    service: str
    action: str
    resource_type: str
    resource_id: str
    project_id: UUID | None
    correlation_id: str | None
    result: Literal["success", "failure", "denied"]
    changes: dict | None       # { field: { old, new } }
    details: dict | None
