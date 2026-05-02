from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_internal
from app.services.audit_store import get_audit_log

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/audit", dependencies=[Depends(require_internal)])
async def get_audit():
    """Аудит-записи для агрегации Auth Service."""
    log = get_audit_log()
    return {"items": log, "total": len(log)}
