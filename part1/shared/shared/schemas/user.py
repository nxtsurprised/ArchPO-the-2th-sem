from __future__ import annotations
from uuid import UUID
from typing import Literal
from pydantic import BaseModel


class ProjectRole(BaseModel):
    project_id: UUID
    role: Literal["pm", "admin", "analyst"]
    side: Literal["customer", "contractor"]


class TokenPayload(BaseModel):
    """JWT payload after decoding"""
    sub: UUID
    org_id: UUID
    roles: list[ProjectRole]
    exp: int
    iat: int
    is_superadmin: bool = False


class UserInfo(BaseModel):
    """Response from Auth /internal/users/:id"""
    id: UUID
    full_name: str
    position: str | None
    org_name: str
    org_side: Literal["customer", "contractor"]
