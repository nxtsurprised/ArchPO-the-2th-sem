from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from shared.schemas.user import TokenPayload

from app.api.deps import get_current_user, require_project_role
from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateResponse
from app.services import template_service
from app.services.audit_service import write_audit

router = APIRouter(tags=["templates"])


def _to_response(tmpl) -> TemplateResponse:
    return TemplateResponse(
        id=tmpl.id,
        type=tmpl.type,
        name=tmpl.name,
        gost_ref=tmpl.gost_ref,
        output_format=tmpl.output_format,
        is_system=tmpl.is_system,
        parent_id=tmpl.parent_id,
        project_id=tmpl.project_id,
        dotx_file_key=tmpl.dotx_file_key,
        formatting=tmpl.formatting,
        sections=tmpl.sections,
        version=tmpl.version,
        created_by=tmpl.created_by,
        created_at=tmpl.created_at,
        updated_at=tmpl.updated_at,
    )


@router.get("/templates")
async def list_templates(
    project_id: str | None = Query(None),
    type: str | None = Query(None),
    user: TokenPayload = Depends(get_current_user),
):
    items = await template_service.list_templates(project_id=project_id, type_filter=type)
    return {"items": [_to_response(t) for t in items], "total": len(items)}


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    user: TokenPayload = Depends(get_current_user),
):
    tmpl = await template_service.get_template(template_id)
    if not tmpl:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Template not found"})
    return _to_response(tmpl)


@router.post("/templates", status_code=201)
async def create_template(
    body: TemplateCreate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    project_id = body.project_id
    if project_id:
        require_project_role(["pm", "admin", "superadmin"], project_id, user)
    elif not user.is_superadmin:
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "Only superadmin can create system templates"})

    tmpl = await template_service.create_template(body, created_by=str(user.sub))
    await write_audit("template.create", "template", tmpl.id, user=user, project_id=project_id, request=request)
    return _to_response(tmpl)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    body: TemplateUpdate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    tmpl = await template_service.get_template(template_id)
    if not tmpl:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Template not found"})

    project_id = tmpl.project_id
    if project_id:
        require_project_role(["pm", "admin", "superadmin"], project_id, user)
    elif not user.is_superadmin:
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "Only superadmin can edit system templates"})

    tmpl = await template_service.update_template(tmpl, body)
    await write_audit("template.update", "template", tmpl.id, user=user, project_id=project_id, request=request)
    return _to_response(tmpl)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    tmpl = await template_service.get_template(template_id)
    if not tmpl:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Template not found"})
    if tmpl.is_system:
        raise HTTPException(409, {"code": "SYSTEM_TEMPLATE", "message": "Cannot delete system template"})

    project_id = tmpl.project_id
    if project_id:
        require_project_role(["pm", "superadmin"], project_id, user)
    elif not user.is_superadmin:
        raise HTTPException(403, {"code": "FORBIDDEN", "message": "Insufficient permissions"})

    await template_service.delete_template(tmpl)
    await write_audit("template.delete", "template", template_id, user=user, project_id=project_id, request=request)
