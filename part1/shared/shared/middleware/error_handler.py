from __future__ import annotations
import structlog
from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = structlog.get_logger()


async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Единый обработчик исключений для всех сервисов.

    Гарантирует, что клиент всегда получает ответ в одном формате:
      { "error": { "code": "...", "message": "...", "details": {} } }

    Три ветки обработки:

    1. HTTPException – намеренно брошенная ошибка из роутера или middleware.
       detail может быть строкой (из сторонних библиотек) или нашим dict
       вида {"code": "...", "message": "...", "details": {}}.

    2. RequestValidationError / ValidationError – Pydantic не смог распарсить
       тело запроса или query-параметры. Возвращаем 422 с подробностями.

    3. Всё остальное – непредвиденная ошибка. Логируем с exc_info для stacktrace,
       клиенту отдаём 500 без внутренних деталей (безопасность).
    """
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            # Наш формат – уже содержит code, message, details
            code = detail.get("code", "HTTP_ERROR")
            message = detail.get("message", str(detail))
            details = detail.get("details", {})
        else:
            # Строковый detail от FastAPI или сторонних библиотек
            code = f"HTTP_{exc.status_code}"
            message = str(detail)
            details = {}
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": message, "details": details}},
        )

    if isinstance(exc, (RequestValidationError, ValidationError)):
        # errors() возвращает список dict с полями loc, msg, type
        errors = exc.errors() if hasattr(exc, "errors") else []
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"errors": errors},
                }
            },
        )

    # Неизвестная ошибка – пишем полный stacktrace в лог, клиенту не раскрываем
    logger.exception("unhandled_exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
                "details": {},
            }
        },
    )
