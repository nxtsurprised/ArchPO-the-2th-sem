from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from shared.schemas.user import TokenPayload

from app.api.deps import get_current_user, require_project_role
from app.models.rates import Rates
from app.schemas.rates import RatesUpdate, RatesResponse
from app.services.audit_service import write_audit

router = APIRouter(tags=["rates"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_response(r: Rates) -> RatesResponse:
    return RatesResponse(
        id=r.id,
        project_id=r.project_id,
        default_rate_per_hour=r.default_rate_per_hour,
        complexity_coefficients=r.complexity_coefficients,
        overhead_coefficient=r.overhead_coefficient,
        vat_rate=r.vat_rate,
        profit_margin=r.profit_margin,
        updated_by=r.updated_by,
        updated_at=r.updated_at,
    )


@router.get("/rates")
async def get_rates(
    project_id: str = Query(...),
    user: TokenPayload = Depends(get_current_user),
):
    rates = await Rates.find_one({"project_id": project_id})
    if not rates:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Rates not found for project"})
    return _to_response(rates)


@router.put("/rates/{project_id}")
async def update_rates(
    project_id: str,
    body: RatesUpdate,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
):
    require_project_role(["pm", "superadmin"], project_id, user)

    updates = {"updated_by": str(user.sub), "updated_at": _now()}
    if body.default_rate_per_hour is not None:
        updates["default_rate_per_hour"] = body.default_rate_per_hour
    if body.complexity_coefficients is not None:
        updates["complexity_coefficients"] = body.complexity_coefficients
    if body.overhead_coefficient is not None:
        updates["overhead_coefficient"] = body.overhead_coefficient
    if body.vat_rate is not None:
        updates["vat_rate"] = body.vat_rate
    if body.profit_margin is not None:
        updates["profit_margin"] = body.profit_margin

    rates = await Rates.find_one({"project_id": project_id})
    if not rates:
        rates = Rates(project_id=project_id, **updates)
        await rates.insert()
    else:
        await rates.set(updates)
    await write_audit("rates.update", "rates", rates.id, user=user, project_id=project_id, request=request)
    return _to_response(rates)
