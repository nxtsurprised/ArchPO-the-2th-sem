from __future__ import annotations
from fastapi import Depends, HTTPException, status, Request

from shared.middleware.jwt_auth import JWTAuth
from shared.services.cache import CacheService
from app.config import get_settings

_cache = CacheService()
_settings = get_settings()
_jwt_auth = JWTAuth(auth_service_url=_settings.AUTH_SERVICE_URL, cache=_cache)


async def get_current_user(token_payload=Depends(_jwt_auth)):
    """Возвращает TokenPayload — используется в защищённых роутерах."""
    return token_payload


def require_internal(request: Request) -> None:
    """Проверяет X-Internal-Secret для /internal/* эндпоинтов."""
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != _settings.INTERNAL_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Invalid internal secret"},
        )
