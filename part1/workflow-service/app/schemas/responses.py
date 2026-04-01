from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class DecisionResponse(BaseModel):
    id: str
    user_id: str
    user_role: str
    user_side: str
    decision_type: str
    comment: str | None
    decided_at: datetime

    model_config = {"from_attributes": True}


class RoundResponse(BaseModel):
    id: str
    round_number: int
    status: str
    final_decision: str | None
    started_at: datetime
    completed_at: datetime | None
    decisions: list[DecisionResponse] = []

    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    id: str
    document_id: str
    project_id: str
    type: str
    status: str
    initiated_by: str
    initiated_by_side: str
    current_round: int
    is_locked: bool
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDetailResponse(ApprovalResponse):
    rounds: list[RoundResponse] = []

    model_config = {"from_attributes": True}


class CommentResponse(BaseModel):
    id: str
    request_id: str
    user_id: str
    text: str
    target_section: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    pending: int
    approved: int
    rejected: int
    revision: int
    total: int


class TaskItem(BaseModel):
    approval_id: str
    document_id: str
    type: str
    status: str
    current_round: int
    initiated_by: str
    project_id: str
    created_at: datetime
