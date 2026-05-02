from uuid import UUID
from fastapi import Request, HTTPException, status
import jwt as pyjwt
from shared.schemas.user import TokenPayload, ProjectRole
from app.config import get_settings
from pathlib import Path


def _load_public_key() -> str:
    return Path(get_settings().JWT_PUBLIC_KEY_PATH).read_text()


async def get_current_user(request: Request) -> TokenPayload:
    """
    FastAPI Dependency – верифицирует JWT access-токен через локальный RSA публичный ключ.
    Auth Service верифицирует токены сам (не через JWKS), так как ключи у него локально.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Требуется авторизация"},
        )

    token = auth_header.split(" ", 1)[1]
    try:
        payload = pyjwt.decode(token, _load_public_key(), algorithms=["RS256"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Недействительный или просроченный токен"},
        )

    roles = [
        ProjectRole(
            project_id=UUID(r["project_id"]),
            role=r["role"],
            side=r["side"],
        )
        for r in payload.get("roles", [])
    ]

    token_payload = TokenPayload(
        sub=UUID(payload["sub"]),
        org_id=UUID(payload["org_id"]),
        roles=roles,
        exp=payload["exp"],
        iat=payload["iat"],
        is_superadmin=payload.get("is_superadmin", False),
    )
    request.state.user = token_payload
    return token_payload


async def require_superadmin(request: Request) -> TokenPayload:
    """
    FastAPI Dependency – проверяет, что пользователь является суперадмином.

    Суперадмин – это не проектная роль, а глобальный флаг is_superadmin в таблице users.
    Используется для эндпоинтов управления организациями, проектами и unified-аудитом.
    """
    user = await get_current_user(request)
    if not user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Требуются права суперадминистратора"},
        )
    return user
