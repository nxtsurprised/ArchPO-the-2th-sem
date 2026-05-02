from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user, require_project_access, TokenPayload
from app.schemas.requests import ApprovalSubmit, DecisionCreate, CommentCreate
from app.schemas.responses import ApprovalDetailResponse, ApprovalResponse, CommentResponse
from app.services import approval_service

router = APIRouter(tags=["approvals"])


@router.post("/approvals", status_code=201, response_model=ApprovalDetailResponse)
async def submit_approval(
    body: ApprovalSubmit,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    role, side = require_project_access(user, body.project_id)
    approval = await approval_service.submit_approval(db, body, user, role, side)
    return approval


@router.get("/approvals", response_model=dict)
async def list_approvals(
    project_id: str | None = Query(None),
    approval_status: str | None = Query(None, alias="status"),
    my: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    user_id_filter = str(user.sub) if my else None
    items, total = await approval_service.list_approvals(
        db, project_id=project_id, approval_status=approval_status,
        user_id=user_id_filter, page=page, per_page=per_page,
    )
    return {
        "items": [ApprovalResponse.model_validate(a) for a in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/approvals/{approval_id}", response_model=ApprovalDetailResponse)
async def get_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    from fastapi import HTTPException
    approval = await approval_service.get_approval(db, approval_id)
    if not approval:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Approval not found"})
    return approval


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalDetailResponse)
async def decide(
    approval_id: str,
    body: DecisionCreate,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    from fastapi import HTTPException
    approval = await approval_service.get_approval(db, approval_id)
    if not approval:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Approval not found"})
    role, side = require_project_access(user, approval.project_id)
    result = await approval_service.decide(db, approval_id, body, user, role, side)
    return result


@router.post("/approvals/{approval_id}/revoke", response_model=ApprovalDetailResponse)
async def revoke_decision(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    from fastapi import HTTPException
    approval = await approval_service.get_approval(db, approval_id)
    if not approval:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Approval not found"})
    role, side = require_project_access(user, approval.project_id)
    result = await approval_service.revoke_decision(db, approval_id, user, role)
    return result


@router.post("/approvals/{approval_id}/cancel", response_model=ApprovalDetailResponse)
async def cancel_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    from fastapi import HTTPException
    approval = await approval_service.get_approval(db, approval_id)
    if not approval:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Approval not found"})
    role, side = require_project_access(user, approval.project_id)
    result = await approval_service.cancel_approval(db, approval_id, user, role)
    return result


@router.get("/approvals/{approval_id}/history", response_model=dict)
async def get_history(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    from fastapi import HTTPException
    from app.schemas.responses import RoundResponse
    approval = await approval_service.get_approval(db, approval_id)
    if not approval:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Approval not found"})
    return {
        "approval_id": approval.id,
        "rounds": [RoundResponse.model_validate(r) for r in approval.rounds],
    }


@router.post("/approvals/{approval_id}/comments", status_code=201, response_model=CommentResponse)
async def add_comment(
    approval_id: str,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    comment = await approval_service.add_comment(db, approval_id, body, user)
    return comment
