from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
import structlog

if TYPE_CHECKING:
    from fastapi import Request
    from shared.schemas.user import TokenPayload

logger = structlog.get_logger()


async def write_audit(
    action: str,
    resource_type: str,
    resource_id: str,
    user: "TokenPayload | None" = None,
    project_id: str | None = None,
    result: str = "success",
    changes: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    request: "Request | None" = None,
) -> None:
    from app.models.audit import AuditLog

    ip_address = "unknown"
    user_agent = None
    correlation_id = None
    user_side = None
    user_role = None

    if request is not None:
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent")
        correlation_id = getattr(request.state, "correlation_id", None)

    if user is not None and project_id:
        for r in user.roles:
            if str(r.project_id) == project_id:
                user_side = r.side
                user_role = r.role
                break

    entry = AuditLog(
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id=str(user.sub) if user else "system",
        user_side=user_side,
        user_role=user_role,
        ip_address=ip_address,
        user_agent=user_agent,
        service="catalog",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        correlation_id=correlation_id,
        result=result,
        changes=changes,
        details=details,
    )

    try:
        await entry.insert()
    except Exception as exc:
        logger.warning("audit_write_failed", error=str(exc))

    logger.info(
        "audit_event",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=entry.user_id,
        result=result,
    )
