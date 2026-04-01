from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class ApprovalSubmit(BaseModel):
    document_id: str
    project_id: str
    type: Literal["tz_final", "nmck_final", "review"]


class DecisionCreate(BaseModel):
    decision: Literal["approve", "reject", "revision", "review"]
    comment: str | None = None


class CommentCreate(BaseModel):
    text: str
    target_section: str | None = None
