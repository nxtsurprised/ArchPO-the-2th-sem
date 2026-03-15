from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from shared.schemas.user import TokenPayload

from app.api.deps import get_current_user, require_project_role
from app.schemas.document import (
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentValidationResponse
)
from app.services import document_service
from app.services.audit_service import write_audit

router = APIRouter(tags=["documents"])

_LOCKED_STATUSES = ("pending", "approved")


def _to_response(doc) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        project_id=doc.project_id,
        template_id=doc.template_id,
        name=doc.name,
        type=doc.type,
        status=doc.status,
        function_ids=doc.function_ids,
        data=doc.data,
        version=doc.version,
        created_by=doc.created_by,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/documents")
async def list_documents(
    project_id: str | None = Query(None),
    type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: TokenPayload = Depends(get_current_user),
):
    items, total = await document_service.list_documents(
        project_id=project_id, type_filter=type, page=page, per_page=per_page
    )
    return {"items": [_to_response(d) for d in items], "total": total, "page": page, "per_page": per_page}


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    user: TokenPayload = Depends(get_current_user),
):
    doc = await document_service.get_document(doc_id)
    if not doc:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Document not found"})
    return _to_response(doc)


@router.post("/documents", status_code=201)
async def create_document(
    body: DocumentCreate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    require_project_role(["pm", "admin", "superadmin"], body.project_id, user)
    doc = await document_service.create_document(body, created_by=str(user.sub))
    await write_audit("document.create", "document", doc.id, user=user, project_id=body.project_id, request=request)
    return _to_response(doc)


@router.put("/documents/{doc_id}")
async def update_document(
    doc_id: str,
    body: DocumentUpdate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    doc = await document_service.get_document(doc_id)
    if not doc:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Document not found"})

    if doc.status in _LOCKED_STATUSES:
        raise HTTPException(
            409,
            {"code": "DOCUMENT_LOCKED", "message": f"Document is locked (status: {doc.status})"},
        )

    require_project_role(["pm", "admin", "analyst", "superadmin"], doc.project_id, user)
    doc = await document_service.update_document(doc, body)
    await write_audit("document.update", "document", doc.id, user=user, project_id=doc.project_id, request=request)
    return _to_response(doc)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    doc = await document_service.get_document(doc_id)
    if not doc:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Document not found"})
    require_project_role(["pm", "superadmin"], doc.project_id, user)
    await document_service.delete_document(doc)
    await write_audit("document.delete", "document", doc_id, user=user, project_id=doc.project_id, request=request)


@router.post("/documents/{doc_id}/validate")
async def validate_document(
    doc_id: str,
    user: TokenPayload = Depends(get_current_user),
):
    doc = await document_service.get_document(doc_id)
    if not doc:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Document not found"})
    result = await document_service.validate_document(doc)
    return DocumentValidationResponse(**result)
