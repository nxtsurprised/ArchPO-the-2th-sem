from __future__ import annotations
from uuid import UUID
from typing import Literal
from datetime import datetime
from pydantic import BaseModel


class WorkflowStatus(BaseModel):
    id: UUID
    document_id: UUID
    status: Literal["pending", "in_review", "approved", "rejected", "revision"]
    created_at: datetime
    updated_at: datetime
