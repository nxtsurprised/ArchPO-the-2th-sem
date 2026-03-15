from __future__ import annotations
from uuid import UUID
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str
    inn: str
    ogrn: str | None = None
    legal_address: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    legal_address: str | None = None


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    inn: str
    ogrn: str | None
    legal_address: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str
    code: str
    description: str | None = None
    customer_org_id: UUID
    contractor_org_id: UUID


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    code: str
    description: str | None
    customer_org_id: UUID
    contractor_org_id: UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    position: str | None = None
    organization_id: UUID


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    position: str | None = None


class RoleAssignment(BaseModel):
    project_id: UUID
    role_name: str


class UserRoleInfo(BaseModel):
    project_id: UUID
    project_name: str
    role: str
    side: Literal["customer", "contractor"]


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    position: str | None
    is_active: bool
    is_2fa_required: bool
    organization_id: UUID
    roles: list[UserRoleInfo] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    position: str | None
    is_2fa_enabled: bool
    password_expires_at: datetime | None
    roles: list[UserRoleInfo] = []
    organization_id: UUID
