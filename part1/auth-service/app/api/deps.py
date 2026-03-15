from __future__ import annotations
from fastapi import Request, HTTPException, status
from shared.schemas.user import TokenPayload


async def get_current_user(request: Request) -> TokenPayload:
    """
    FastAPI Dependency – извлекает авторизованного пользователя из контекста запроса.

    JWTAuth middleware (подключённый в main.py для защищённых роутеров) записывает
    разобранный TokenPayload в request.state.user после успешной верификации токена.
    Если токен не был проверен (роутер не требует аутентификации или middleware не
    отработал), user будет None и функция вернёт 401.

    Использование в роутере:
        token: TokenPayload = Depends(get_current_user)
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Требуется авторизация"},
        )
    return user


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
