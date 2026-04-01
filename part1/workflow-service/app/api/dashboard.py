from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user, require_project_access, TokenPayload
from app.schemas.responses import DashboardResponse, TaskItem
from app.services import approval_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    project_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    require_project_access(user, project_id)
    counts = await approval_service.get_dashboard(db, project_id)
    return DashboardResponse(**counts)


@router.get("/my-tasks", response_model=list[TaskItem])
async def my_tasks(
    project_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: TokenPayload = Depends(get_current_user),
):
    role, side = require_project_access(user, project_id)
    tasks = await approval_service.get_my_tasks(db, user, project_id, role, side)
    return [
        TaskItem(
            approval_id=a.id,
            document_id=a.document_id,
            type=a.type,
            status=a.status,
            current_round=a.current_round,
            initiated_by=a.initiated_by,
            project_id=a.project_id,
            created_at=a.created_at,
        )
        for a in tasks
    ]
