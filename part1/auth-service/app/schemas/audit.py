from __future__ import annotations
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    timestamp: datetime
    user_id: UUID
    user_side: str | None
    user_role: str | None
    ip_address: str | None
    user_agent: str | None
    service: str
    action: str
    resource_type: str
    resource_id: str
    project_id: UUID | None
    correlation_id: str | None
    result: str
    changes: dict | None
    details: dict | None

    model_config = {"from_attributes": True}
