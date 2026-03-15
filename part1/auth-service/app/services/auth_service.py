from __future__ import annotations
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, Request, status

from app.models.user import User, UserProjectRole, Project, Role
from app.models.session import Session
from app.models.totp import TotpDevice
from app.services.password import verify_password
from app.services.jwt_service import create_access_token, create_refresh_token
from app.services.audit_service import AuthAuditLogger
from app.config import get_settings

import pyotp
import structlog

logger = structlog.get_logger()


async def get_user_roles_for_jwt(db: AsyncSession, user: User) -> list[dict]:
    """
    Собирает список ролей пользователя по всем проектам для вставки в JWT payload.

    Сторона (side) не хранится в БД – она вычисляется здесь динамически:
    сравниваем organization_id пользователя с customer_org_id / contractor_org_id проекта.
    Если организация пользователя не фигурирует ни в одной стороне проекта
    (ситуация, которая не должна возникать в норме), такую роль пропускаем.
    """
    stmt = (
        select(UserProjectRole, Project, Role)
        .join(Project, UserProjectRole.project_id == Project.id)
        .join(Role, UserProjectRole.role_id == Role.id)
        .where(UserProjectRole.user_id == user.id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    roles = []
    for upr, project, role in rows:
        # Определяем сторону пользователя в этом проекте
        if user.organization_id == project.customer_org_id:
            side = "customer"
        elif user.organization_id == project.contractor_org_id:
            side = "contractor"
        else:
            # Организация пользователя не участвует в этом проекте – пропускаем
            continue
        roles.append({
            "project_id": str(upr.project_id),
            "role": role.name,    # "pm" / "admin" / "analyst"
            "side": side,         # "customer" / "contractor"
        })
    return roles


async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
    totp_code: str | None,
    request: Request,
) -> dict:
    """
    Основная логика входа в систему. Последовательность проверок:

    1. Существование пользователя – если не найден, возвращаем 401
       (не раскрываем факт отсутствия аккаунта).
    2. Блокировка аккаунта (locked_until) – 423 Locked.
    3. Активность аккаунта – 401 для деактивированных.
    4. Прогрессивная задержка – растёт экспоненциально с числом неудачных попыток,
       снижает эффективность брутфорса.
    5. Проверка пароля через Argon2id.
    6. 2FA – если is_2fa_required и есть активное TOTP-устройство, код обязателен.
    7. Сброс счётчика неудачных попыток после успешного входа.
    8. Вытеснение самой старой сессии при превышении MAX_CONCURRENT_SESSIONS.
    9. Выпуск access + refresh токенов, создание записи сессии.
    """
    settings = get_settings()
    audit = AuthAuditLogger(db)

    # Шаг 1 – поиск пользователя по email
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        # Логируем попытку, но не раскрываем, что аккаунта нет – всегда 401
        await audit.log(
            action="login.attempt", resource_type="user", resource_id=email,
            result="failure", details={"reason": "user_not_found"}, request=request,
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "code": "INVALID_CREDENTIALS", "message": "Неверный email или пароль",
        })

    # Сравниваем datetime без timezone, так как PostgreSQL хранит без tz
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Шаг 2 – проверка блокировки
    if user.locked_until and user.locked_until > now:
        await audit.log(
            action="login.attempt", resource_type="user", resource_id=str(user.id),
            user_id=user.id, result="denied", details={"reason": "account_locked"}, request=request,
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={
            "code": "ACCOUNT_LOCKED", "message": "Аккаунт заблокирован. Попробуйте позже.",
        })

    # Шаг 3 – аккаунт должен быть активен
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "code": "ACCOUNT_INACTIVE", "message": "Аккаунт деактивирован",
        })

    # Шаг 4 – прогрессивная задержка: 0, 1, 2, 4 ... 8 с (максимум)
    attempts = user.failed_login_attempts or 0
    if attempts > 0:
        import asyncio
        delay = min(2 ** (attempts - 1), 8)
        await asyncio.sleep(delay)

    # Шаг 5 – проверка пароля
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            # Достигли порога – блокируем аккаунт на LOCKOUT_DURATION_SECONDS (30 мин)
            user.locked_until = (
                datetime.now(timezone.utc) + timedelta(seconds=settings.LOCKOUT_DURATION_SECONDS)
            ).replace(tzinfo=None)
            await audit.log(
                action="login.account_locked", resource_type="user", resource_id=str(user.id),
                user_id=user.id, result="failure", request=request,
            )
        else:
            await audit.log(
                action="login.attempt", resource_type="user", resource_id=str(user.id),
                user_id=user.id, result="failure",
                details={"reason": "invalid_password", "attempts": user.failed_login_attempts},
                request=request,
            )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "code": "INVALID_CREDENTIALS", "message": "Неверный email или пароль",
        })

    # Шаг 6 – двухфакторная аутентификация
    if user.is_2fa_required:
        totp_stmt = select(TotpDevice).where(
            and_(TotpDevice.user_id == user.id, TotpDevice.is_active == True)
        )
        totp_result = await db.execute(totp_stmt)
        totp_device = totp_result.scalar_one_or_none()

        if totp_device and not totp_code:
            # Пользователь ввёл только пароль, но 2FA обязательна
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
                "code": "TOTP_REQUIRED", "message": "Требуется код двухфакторной аутентификации",
            })

        if totp_device and totp_code:
            from app.services.crypto import decrypt_totp
            secret = decrypt_totp(totp_device.secret_encrypted)
            # valid_window=1 разрешает коды ±30 секунд от текущего окна
            if not pyotp.TOTP(secret).verify(totp_code, valid_window=1):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
                    "code": "INVALID_TOTP", "message": "Неверный код 2FA",
                })

    # Шаг 7 – успешный вход: сбрасываем счётчик неудачных попыток
    user.failed_login_attempts = 0
    user.locked_until = None

    # Шаг 8 – контроль числа активных сессий
    # Берём активные сессии, отсортированные по дате создания (самая старая – первая)
    sessions_stmt = select(Session).where(
        and_(Session.user_id == user.id, Session.is_revoked == False)
    ).order_by(Session.created_at.asc())
    sessions_result = await db.execute(sessions_stmt)
    active_sessions = sessions_result.scalars().all()

    if len(active_sessions) >= settings.MAX_CONCURRENT_SESSIONS:
        # Вытесняем самую старую сессию
        active_sessions[0].is_revoked = True

    # Шаг 9 – выпуск токенов
    roles = await get_user_roles_for_jwt(db, user)
    access_token, exp = create_access_token(
        user_id=str(user.id),
        org_id=str(user.organization_id),
        roles=roles,
        is_superadmin=user.is_superadmin,
    )
    raw_refresh, hashed_refresh = create_refresh_token()

    # Сохраняем только хеш refresh-токена – оригинал уходит клиенту в cookie
    db.add(Session(
        user_id=user.id,
        refresh_token_hash=hashed_refresh,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        expires_at=(
            datetime.now(timezone.utc) + timedelta(seconds=settings.JWT_REFRESH_TTL_SECONDS)
        ).replace(tzinfo=None),
    ))

    await audit.log(
        action="login.success", resource_type="user", resource_id=str(user.id),
        user_id=user.id, result="success", request=request,
    )
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,  # вернётся клиенту в httpOnly cookie
        "expires_in": settings.JWT_ACCESS_TTL_SECONDS,
    }


async def refresh_tokens(db: AsyncSession, refresh_token: str, request: Request) -> dict:
    """
    Ротация refresh-токена: старый инвалидируется, выпускается новая пара токенов.

    Ротация – мера безопасности: если злоумышленник перехватил refresh-токен
    и использует его, легитимный пользователь при следующей попытке обнаружит 401
    (старый токен уже revoked), что сигнализирует о компрометации сессии.
    """
    settings = get_settings()

    # Хешируем входящий токен и ищем соответствующую сессию
    hashed = hashlib.sha256(refresh_token.encode()).hexdigest()

    stmt = select(Session).where(
        and_(Session.refresh_token_hash == hashed, Session.is_revoked == False)
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "code": "INVALID_REFRESH_TOKEN", "message": "Недействительный refresh-токен",
        })

    # Проверяем срок жизни сессии (7 дней по умолчанию)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if session.expires_at < now:
        session.is_revoked = True
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "code": "REFRESH_TOKEN_EXPIRED", "message": "Refresh-токен истёк",
        })

    user_stmt = select(User).where(User.id == session.user_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={
            "code": "USER_INACTIVE", "message": "Пользователь неактивен",
        })

    # Инвалидируем использованный refresh-токен (ротация)
    session.is_revoked = True

    # Создаём новую сессию с новым refresh-токеном
    raw_refresh, hashed_refresh = create_refresh_token()
    db.add(Session(
        user_id=user.id,
        refresh_token_hash=hashed_refresh,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        expires_at=(
            datetime.now(timezone.utc) + timedelta(seconds=settings.JWT_REFRESH_TTL_SECONDS)
        ).replace(tzinfo=None),
    ))

    # Перегенерируем access-токен (роли могли измениться с прошлого логина)
    roles = await get_user_roles_for_jwt(db, user)
    access_token, exp = create_access_token(
        user_id=str(user.id),
        org_id=str(user.organization_id),
        roles=roles,
        is_superadmin=user.is_superadmin,
    )
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "expires_in": settings.JWT_ACCESS_TTL_SECONDS,
    }


async def logout_user(db: AsyncSession, refresh_token: str | None, user_id: UUID) -> None:
    """
    Инвалидирует сессии пользователя.

    Если refresh_token передан – отзывается только конкретная сессия
    (выход с одного устройства). Если не передан – отзываются все сессии
    (выход со всех устройств).
    """
    if refresh_token:
        # Находим сессию по хешу токена, принадлежащую именно этому пользователю
        hashed = hashlib.sha256(refresh_token.encode()).hexdigest()
        stmt = select(Session).where(
            and_(Session.refresh_token_hash == hashed, Session.user_id == user_id)
        )
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session:
            session.is_revoked = True
    else:
        # Отзываем все активные сессии – "выйти со всех устройств"
        stmt = select(Session).where(
            and_(Session.user_id == user_id, Session.is_revoked == False)
        )
        for s in (await db.execute(stmt)).scalars().all():
            s.is_revoked = True

    await db.commit()
