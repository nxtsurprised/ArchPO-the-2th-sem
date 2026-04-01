from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.api.deps import verify_internal_secret
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog

router = APIRouter(tags=["internal"])


@router.get(
    "/internal/documents/{document_id}/status",
    dependencies=[Depends(verify_internal_secret)],
)
async def document_status(document_id: str, db: AsyncSession = Depends(get_db)):
    """
    Used by Catalog Service to check if a document is locked before allowing edits.
    Returns the most recent non-cancelled approval status for this document.
    """
    result = await db.execute(
        select(ApprovalRequest)
        .where(
            and_(
                ApprovalRequest.document_id == document_id,
                ApprovalRequest.status != "cancelled",
            )
        )
        .order_by(ApprovalRequest.created_at.desc())
    )
    approval = result.scalars().first()

    if not approval:
        return {"status": "draft", "locked": False}

    return {
        "status": approval.status,
        "locked": approval.is_locked,
        "approval_id": approval.id,
        "type": approval.type,
        "current_round": approval.current_round,
    }


@router.get(
    "/internal/audit",
    dependencies=[Depends(verify_internal_secret)],
)
async def internal_audit(
    project_id: str | None = Query(None),
    user_id: str | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(1000)
    filters = []
    if project_id:
        filters.append(AuditLog.project_id == project_id)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if from_dt:
        filters.append(AuditLog.timestamp >= from_dt)
    if to_dt:
        filters.append(AuditLog.timestamp <= to_dt)
    if filters:
        q = q.where(and_(*filters))

    result = await db.execute(q)
    entries = result.scalars().all()
    return {
        "items": [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "user_id": e.user_id,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "project_id": e.project_id,
                "result": e.result,
                "details": e.details,
            }
            for e in entries
        ]
    }
