from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from shared.schemas.user import TokenPayload

from app.api.deps import get_current_user, require_project_role
from app.schemas.function import FunctionCreate, FunctionUpdate, FunctionResponse
from app.services import function_service
from app.services.audit_service import write_audit

router = APIRouter(tags=["functions"])


def _to_response(fn) -> FunctionResponse:
    return FunctionResponse(
        id=fn.id,
        project_id=fn.project_id,
        subsystem_id=fn.subsystem_id,
        code=fn.code,
        name=fn.name,
        category=fn.category,
        priority=fn.priority,
        status=fn.status,
        description=fn.description,
        requirements=[r if isinstance(r, dict) else r.model_dump() for r in fn.requirements],
        input_data=fn.input_data,
        output_data=fn.output_data,
        constraints=fn.constraints,
        dependencies=fn.dependencies,
        complexity=fn.complexity,
        cost_params=fn.cost_params.model_dump() if hasattr(fn.cost_params, "model_dump") else fn.cost_params,
        test_params=fn.test_params.model_dump() if hasattr(fn.test_params, "model_dump") else fn.test_params,
        doc_refs=fn.doc_refs.model_dump() if hasattr(fn.doc_refs, "model_dump") else fn.doc_refs,
        tags=fn.tags,
        version=fn.version,
        created_by=fn.created_by,
        created_at=fn.created_at,
        updated_at=fn.updated_at,
    )


@router.get("/functions")
async def list_functions(
    project_id: str | None = Query(None),
    category: str | None = Query(None),
    subsystem_id: str | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: TokenPayload = Depends(get_current_user),
):
    items, total = await function_service.list_functions(
        project_id=project_id,
        category=category,
        subsystem_id=subsystem_id,
        q=q,
        page=page,
        per_page=per_page,
    )
    return {"items": [_to_response(fn) for fn in items], "total": total, "page": page, "per_page": per_page}


@router.get("/functions/{function_id}")
async def get_function(
    function_id: str,
    user: TokenPayload = Depends(get_current_user),
):
    fn = await function_service.get_function(function_id)
    if not fn:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Function not found"})
    return _to_response(fn)


@router.post("/functions", status_code=201)
async def create_function(
    body: FunctionCreate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    require_project_role(["pm", "analyst", "superadmin"], body.project_id, user)
    fn = await function_service.create_function(body, created_by=str(user.sub))
    await write_audit("function.create", "function", fn.id, user=user, project_id=body.project_id, request=request)
    return _to_response(fn)


@router.put("/functions/{function_id}")
async def update_function(
    function_id: str,
    body: FunctionUpdate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    fn = await function_service.get_function(function_id)
    if not fn:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Function not found"})

    project_id = fn.project_id
    role = None
    from app.api.deps import get_user_role_in_project
    role = get_user_role_in_project(user, project_id)

    # Info fields: pm, analyst, superadmin
    require_project_role(["pm", "analyst", "superadmin"], project_id, user)

    # Cost and priority fields: pm only
    cost_fields_touched = body.cost_params is not None or body.complexity is not None or body.priority is not None
    if cost_fields_touched and role not in ("pm", "superadmin"):
        raise HTTPException(
            403,
            {"code": "FORBIDDEN", "message": "Only pm can edit cost and priority fields"},
        )

    fn = await function_service.update_function(fn, body)
    await write_audit("function.update", "function", fn.id, user=user, project_id=project_id, request=request)
    return _to_response(fn)


@router.delete("/functions/{function_id}", status_code=204)
async def delete_function(
    function_id: str,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    fn = await function_service.get_function(function_id)
    if not fn:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Function not found"})

    require_project_role(["pm", "superadmin"], fn.project_id, user)
    await function_service.soft_delete_function(fn)
    await write_audit("function.delete", "function", function_id, user=user, project_id=fn.project_id, request=request)
