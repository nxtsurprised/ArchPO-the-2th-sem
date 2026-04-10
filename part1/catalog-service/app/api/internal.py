from __future__ import annotations
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import verify_internal_secret
from app.models.audit import AuditLog
from app.services.document_service import get_document, get_render_bundle
from app.services.function_service import list_functions

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
    "/internal/pmi-functions",
    dependencies=[Depends(verify_internal_secret)],
)
async def get_pmi_functions(project_id: str = Query(...)):
    """Return all active functions for a project — used by pmi-agent."""
    items, _ = await list_functions(project_id=project_id, per_page=1000)
    return {
        "items": [
            {
                "id": fn.id,
                "code": fn.code,
                "name": fn.name,
                "description": fn.description,
                "acceptance_criteria": [c.text for c in fn.test_params.criteria],
                "requirements": [r.text for r in fn.requirements],
            }
            for fn in items
        ]
    }


class PMIResultsRequest(BaseModel):
    sections: dict[str, Any]  # {function_id: pmi_section_dict}


@router.put(
    "/internal/documents/{doc_id}/pmi-results",
    dependencies=[Depends(verify_internal_secret)],
)
async def save_pmi_results(doc_id: str, body: PMIResultsRequest):
    """Write PMI agent results back into a document's data.sections."""
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Document not found"})

    existing_data = doc.data or {}
    existing_sections = existing_data.get("sections", {})
    existing_sections.update({"pmi_results": body.sections})
    doc.data = {**existing_data, "sections": existing_sections}
    await doc.save()
    return {"ok": True}


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
