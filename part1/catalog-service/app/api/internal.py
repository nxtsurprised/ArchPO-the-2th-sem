from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import verify_internal_secret
from app.models.audit import AuditLog
from app.services.document_service import get_document, get_render_bundle

router = APIRouter(tags=["internal"])


@router.get(
    "/internal/documents/{doc_id}/render-bundle",
    dependencies=[Depends(verify_internal_secret)],
)
async def render_bundle(doc_id: str):
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Document not found"})
    bundle = await get_render_bundle(doc)
    return bundle


@router.get(
    "/internal/audit",
    dependencies=[Depends(verify_internal_secret)],
)
async def internal_audit(
    project_id: str | None = Query(None),
    user_id: str | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if user_id:
        query["user_id"] = user_id
    if from_dt:
        query["timestamp"] = {"$gte": from_dt.isoformat()}
    if to_dt:
        existing = query.get("timestamp", {})
        existing["$lte"] = to_dt.isoformat()
        query["timestamp"] = existing

    entries = await AuditLog.find(query).sort("-timestamp").limit(1000).to_list()
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
            }
            for e in entries
        ]
    }
