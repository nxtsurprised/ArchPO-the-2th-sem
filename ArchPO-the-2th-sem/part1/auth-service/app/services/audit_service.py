from __future__ import annotations
import uuid
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from app.models.audit import AuditLog


class AuthAuditLogger:
    """
    Сервис записи аудит-событий в таблицу audit_log.

    Принцип работы: запись в audit_log выполняется через flush() (а не commit()),
    что позволяет включить её в ту же транзакцию, что и бизнес-операцию.
    Если транзакция откатится – аудит-запись тоже откатится. Это исключает ситуацию,
    когда операция не выполнилась, а запись в аудите появилась (или наоборот).

    Таблица audit_log – append-only: приложение имеет только INSERT,
    поэтому записи не могут быть изменены или удалены через штатный код.

    Параметры action именуются по схеме resource.verb, например:
      login.success, login.attempt, user.created, user.role_assigned
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: UUID | str | None = None,
        user_side: str | None = None,
        user_role: str | None = None,
        result: str = "success",       # "success" / "failure" / "denied"
        changes: dict | None = None,   # { field: { old, new } } – для событий изменения данных
        details: dict | None = None,   # произвольный контекст события
        project_id: UUID | None = None,
        request: Request | None = None,
    ) -> None:
        # Извлекаем сетевой контекст запроса для криминалистики
        ip_address = "unknown"
        user_agent = None
        correlation_id = None

        if request is not None:
            ip_address = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("User-Agent")
            # correlation_id добавил correlation_id_middleware в request.state
            correlation_id = getattr(request.state, "correlation_id", None)

        # Если действие выполняется системой (например, seed), используем nil UUID
        _user_id = UUID(str(user_id)) if user_id else UUID("00000000-0000-0000-0000-000000000000")

        entry = AuditLog(
            id=uuid.uuid4(),
            # replace(tzinfo=None) – PostgreSQL хранит DateTime без tz, убираем offset
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            user_id=_user_id,
            user_side=user_side,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            service="auth",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            project_id=project_id,
            correlation_id=correlation_id,
            result=result,
            changes=changes,
            details=details,
        )
        self.db.add(entry)
        # flush отправляет INSERT в БД, но не коммитит транзакцию –
        # запись станет видна другим только после явного commit() вызывающего кода
        await self.db.flush()
