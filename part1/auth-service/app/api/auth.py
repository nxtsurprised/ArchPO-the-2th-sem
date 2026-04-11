from __future__ import annotations
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, PasswordResetRequest, PasswordResetConfirm
from app.services.auth_service import login_user, refresh_tokens, logout_user
from app.api.deps import get_current_user
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # Вся логика аутентификации (проверка пароля, 2FA, сессии) вынесена в auth_service
    result = await login_user(db, body.email, body.password, body.totp_code, request)

    # Refresh-токен передаётся только через httpOnly cookie –
    # JavaScript не может его прочитать, что защищает от XSS-атак.
    # path="/api/auth/refresh" ограничивает область видимости cookie единственным
    # маршрутом обновления, не отправляя токен с каждым запросом.
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=False,        # В production должно быть True (HTTPS-only)
        samesite="lax",
        max_age=604800,      # 7 дней – совпадает с JWT_REFRESH_TTL_SECONDS
        path="/api/auth/refresh",
    )
    # В теле ответа возвращаем только access-токен (короткоживущий, 15 мин)
    return TokenResponse(access_token=result["access_token"], expires_in=result["expires_in"])


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    # FastAPI автоматически извлекает значение cookie "refresh_token" через параметр Cookie
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "code": "MISSING_REFRESH_TOKEN", "message": "Refresh-токен отсутствует",
        })

    # Ротация: старый токен инвалидируется, выпускается новая пара
    result = await refresh_tokens(db, refresh_token, request)

    # Перезаписываем cookie новым refresh-токеном
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=604800,
        path="/api/auth/refresh",
    )
    return TokenResponse(access_token=result["access_token"], expires_in=result["expires_in"])


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    # Получаем идентификатор пользователя из access-токена (заголовок Authorization)
    token = await get_current_user(request)
    # Отзываем сессию (одну – по refresh-токену, или все – если cookie нет)
    await logout_user(db, refresh_token, token.sub)
    # Удаляем cookie с клиента – браузер больше не будет отправлять токен
    response.delete_cookie("refresh_token")


@router.post("/password/reset-request", status_code=200)
@limiter.limit("5/minute")
async def password_reset_request(request: Request, body: PasswordResetRequest):
    # Всегда возвращаем 200 независимо от того, существует ли аккаунт.
    # Так злоумышленник не может перебором выяснить, какие email зарегистрированы.
    # В MVP реальная отправка письма не реализована.
    return {"message": "Если аккаунт существует, инструкции отправлены на email"}


@router.post("/password/reset-confirm")
async def password_reset_confirm(body: PasswordResetConfirm):
    # MVP-заглушка: подтверждение сброса по токену из письма не реализовано
    raise HTTPException(status_code=400, detail={
        "code": "NOT_IMPLEMENTED",
        "message": "Сброс пароля по токену не реализован в MVP",
    })
