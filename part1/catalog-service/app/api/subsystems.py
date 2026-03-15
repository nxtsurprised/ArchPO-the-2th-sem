from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from shared.schemas.user import TokenPayload

from app.api.deps import get_current_user, require_project_role
from app.models.subsystem import Subsystem
from app.schemas.subsystem import SubsystemCreate, SubsystemUpdate, SubsystemReorder, SubsystemResponse
from app.services.audit_service import write_audit

router = APIRouter(tags=["subsystems"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_response(s: Subsystem) -> SubsystemResponse:
    return SubsystemResponse(
        id=s.id,
        project_id=s.project_id,
        code=s.code,
        name=s.name,
        description=s.description,
        order=s.order,
        tz_section_prefix=s.tz_section_prefix,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("/subsystems")
async def list_subsystems(
    project_id: str | None = Query(None),
    user: TokenPayload = Depends(get_current_user),
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    items = await Subsystem.find(query).sort("+order").to_list()
    return {"items": [_to_response(s) for s in items], "total": len(items)}


@router.post("/subsystems", status_code=201)
async def create_subsystem(
    body: SubsystemCreate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    require_project_role(["pm", "superadmin"], body.project_id, user)
    now = _now()
    s = Subsystem(
        project_id=body.project_id,
        code=body.code,
        name=body.name,
        description=body.description,
        order=body.order,
        tz_section_prefix=body.tz_section_prefix,
        created_at=now,
        updated_at=now,
    )
    await s.insert()
    await write_audit("subsystem.create", "subsystem", s.id, user=user, project_id=body.project_id, request=request)
    return _to_response(s)


@router.put("/subsystems/reorder")
async def reorder_subsystems(
    body: SubsystemReorder,
    project_id: str = Query(...),
    request: Request = None,
    user: TokenPayload = Depends(get_current_user),
):
    require_project_role(["pm", "superadmin"], project_id, user)
    for order, sid in enumerate(body.ids):
        s = await Subsystem.get(sid)
        if s and s.project_id == project_id:
            await s.set({"order": order, "updated_at": _now()})
    return {"ok": True}


@router.put("/subsystems/{subsystem_id}")
async def update_subsystem(
    subsystem_id: str,
    body: SubsystemUpdate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    s = await Subsystem.get(subsystem_id)
    if not s:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Subsystem not found"})
    require_project_role(["pm", "superadmin"], s.project_id, user)

    updates = {"updated_at": _now()}
    for field in ("code", "name", "description", "order", "tz_section_prefix"):
        val = getattr(body, field)
        if val is not None:
            updates[field] = val
    await s.set(updates)
    await write_audit("subsystem.update", "subsystem", s.id, user=user, project_id=s.project_id, request=request)
    return _to_response(s)


@router.delete("/subsystems/{subsystem_id}", status_code=204)
async def delete_subsystem(
    subsystem_id: str,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    s = await Subsystem.get(subsystem_id)
    if not s:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Subsystem not found"})
    require_project_role(["pm", "superadmin"], s.project_id, user)

    from app.models.function import Function
    fn_count = await Function.find(
        {"project_id": s.project_id, "subsystem_id": s.id, "status": {"$ne": "deleted"}}
    ).count()
    if fn_count > 0:
        raise HTTPException(
            409,
            {"code": "HAS_FUNCTIONS", "message": "Cannot delete subsystem with active functions"},
        )
    await s.delete()
    await write_audit("subsystem.delete", "subsystem", subsystem_id, user=user, project_id=s.project_id, request=request)
