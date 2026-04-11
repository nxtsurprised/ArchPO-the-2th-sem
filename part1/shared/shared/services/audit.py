"""
Единый аудит-логгер для всех сервисов.

Архитектурное решение — локальный аудит в каждом сервисе:
  Каждый сервис пишет аудит-события в свою БД в рамках той же транзакции,
  что и бизнес-операция. Это гарантирует атомарность: либо и операция, и
  аудит-запись сохранены, либо ни то, ни другое.

  Альтернатива — централизованный Audit Service — отложена на v2 (через Kafka).
  Там атомарность обеспечивается иначе (transactional outbox), но это сложнее.

Текущая реализация пишет в structlog. Конкретные сервисы могут расширить
класс или передать session_factory для записи непосредственно в БД.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
import structlog
from datetime import datetime, timezone

if TYPE_CHECKING:
    from fastapi import Request
    from shared.schemas.user import TokenPayload

logger = structlog.get_logger()


class AuditLogger:
    """
    Записывает аудит-событие: кто, что сделал, с каким результатом.

    Параметр user=None используется для системных операций (фоновые задачи,
    seed-скрипты), в этом случае user_id записывается как "system".
    """

    def __init__(self, service_name: str, session_factory=None):
        self.service_name = service_name
        self._session_factory = session_factory

    async def log(
        self,
        action: str,
        user: "TokenPayload | None",
        resource_type: str,
        resource_id: str,
        result: str = "success",
        changes: dict | None = None,
        details: dict | None = None,
        request: "Request | None" = None,
        project_id=None,
        user_side: str | None = None,
        user_role: str | None = None,
    ) -> None:
        ip_address = "unknown"
        user_agent = None
        correlation_id = None

        if request is not None:
            ip_address = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("User-Agent")
            # correlation_id проставлен CorrelationIdMiddleware ранее в цепочке запроса
            correlation_id = getattr(request.state, "correlation_id", None)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": str(user.sub) if user else "system",
            "user_side": user_side,
            "user_role": user_role,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "service": self.service_name,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "project_id": str(project_id) if project_id else None,
            "correlation_id": correlation_id,
            "result": result,        # "success" | "failure" | "denied"
            "changes": changes,      # { field: { old, new } } от audit_diff.compute_changes()
            "details": details,      # произвольный контекст операции
        }

        logger.info("audit_event", **entry)
