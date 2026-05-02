from __future__ import annotations
from typing import Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = structlog.get_logger()


async def write_audit(
    db: AsyncSession,
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    project_id: str | None = None,
    result: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        result=result,
        details=details or {},
    )
    db.add(entry)
    # commit handled by caller
    logger.info("audit", action=action, user_id=user_id, resource_id=resource_id)
