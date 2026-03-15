from __future__ import annotations
import uuid
from fastapi import Request
from starlette.responses import Response
import structlog

logger = structlog.get_logger()


async def correlation_id_middleware(request: Request, call_next) -> Response:
    """
    Middleware сквозной трассировки запросов через все сервисы.

    Логика:
      - Если клиент (или вышестоящий сервис) передал X-Request-ID – используем его.
        Это позволяет пробрасывать один ID через цепочку microservice-вызовов.
      - Если заголовок отсутствует – генерируем новый UUID.

    correlation_id привязывается к contextvars structlog, поэтому он автоматически
    появляется во всех лог-записях, создаваемых в рамках этого запроса.
    После ответа он отвязывается, чтобы не утечь в следующий запрос (важно при
    использовании пула потоков/корутин).
    """
    # Берём из заголовка или генерируем новый
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # Доступен роутерам через request.state.correlation_id
    request.state.correlation_id = correlation_id

    # Все последующие вызовы structlog.get_logger().info(...) в этом контексте
    # автоматически добавят поле correlation_id в JSON-запись
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    response = await call_next(request)

    # Возвращаем ID в ответе, чтобы клиент мог коррелировать запрос с логами
    response.headers["X-Request-ID"] = correlation_id

    # Очищаем contextvars, чтобы ID не попал в чужой запрос
    structlog.contextvars.unbind_contextvars("correlation_id")
    return response
