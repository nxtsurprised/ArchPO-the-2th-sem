from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
import pyotp

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserProjectRole, Project, Role
from app.models.totp import TotpDevice
from app.models.password_history import PasswordHistory
from app.schemas.user import MeResponse, UserUpdate, UserRoleInfo
from app.schemas.auth import ChangePasswordRequest
from app.services.password import verify_password, hash_password, validate_password_policy
from app.services.crypto import encrypt_totp, decrypt_totp, encrypt_phone
from app.services.audit_service import AuthAuditLogger
from shared.schemas.user import TokenPayload

router = APIRouter(prefix="/api/auth/me", tags=["me"])


async def _build_roles(db: AsyncSession, user: User) -> list[UserRoleInfo]:
    """
    Собирает список ролей текущего пользователя по всем проектам.

    Side вычисляется динамически через сравнение organization_id с полями проекта,
    чтобы не хранить его в БД.
    """
    stmt = (
        select(UserProjectRole, Project, Role)
        .join(Project, UserProjectRole.project_id == Project.id)
        .join(Role, UserProjectRole.role_id == Role.id)
        .where(UserProjectRole.user_id == user.id)
    )
    rows = (await db.execute(stmt)).all()
    result = []
    for upr, project, role in rows:
        side = "customer" if user.organization_id == project.customer_org_id else "contractor"
        result.append(UserRoleInfo(
            project_id=project.id, project_name=project.name, role=role.name, side=side,
        ))
    return result


@router.get("", response_model=MeResponse)
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Профиль текущего авторизованного пользователя.

    Проверяет наличие активного TOTP-устройства и возвращает флаг is_2fa_enabled,
    чтобы фронтенд знал, показывать ли кнопку настройки 2FA.
    """
    user = (await db.execute(select(User).where(User.id == token.sub))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Пользователь не найден"})

    # Проверяем наличие активного устройства (не просто созданного через /setup)
    totp_active = (await db.execute(
        select(TotpDevice).where(and_(TotpDevice.user_id == user.id, TotpDevice.is_active == True))
    )).scalar_one_or_none() is not None

    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        position=user.position,
        is_2fa_enabled=totp_active,
        password_expires_at=user.password_expires_at,
        roles=await _build_roles(db, user),
        organization_id=user.organization_id,
    )


@router.put("/profile")
async def update_profile(
    body: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Обновление профиля текущего пользователя (ФИО, должность, телефон).

    Телефон шифруется AES-256 перед сохранением – в БД хранится только зашифрованное значение.
    В аудит пишутся только фактически изменившиеся поля (changes).
    """
    user = (await db.execute(select(User).where(User.id == token.sub))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Пользователь не найден"})

    audit = AuthAuditLogger(db)
    # Сохраняем старые значения до изменений для записи diff в аудит
    old = {"full_name": user.full_name, "position": user.position}

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.position is not None:
        user.position = body.position
    if body.phone is not None:
        # Телефон шифруется отдельным ключом (PHONE_ENCRYPTION_KEY)
        user.phone_encrypted = encrypt_phone(body.phone)

    new = {"full_name": user.full_name, "position": user.position}
    # Формируем diff: { field: { old: ..., new: ... } } – только изменившиеся поля
    changes = {k: {"old": old[k], "new": new[k]} for k in old if old[k] != new[k]}
    await audit.log(
        action="user.profile_updated", resource_type="user", resource_id=str(user.id),
        user_id=user.id, changes=changes or None, request=request,
    )
    await db.commit()
    return {"message": "Профиль обновлён"}


@router.put("/password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Смена пароля текущего пользователя.

    Последовательность проверок:
    1. Текущий пароль верен (Argon2id verify).
    2. Новый пароль соответствует политике сложности.
    3. Новый пароль не совпадает ни с одним из последних N паролей (history).
    4. Старый хеш сохраняется в password_history для защиты от повторного использования.
    5. Срок действия пароля сбрасывается на PASSWORD_EXPIRY_DAYS от текущего момента.
    """
    from app.config import get_settings
    from datetime import datetime, timezone, timedelta
    settings = get_settings()

    user = (await db.execute(select(User).where(User.id == token.sub))).scalar_one_or_none()
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail={"code": "INVALID_PASSWORD", "message": "Неверный текущий пароль"})

    errors = validate_password_policy(body.new_password, user.email, user.full_name)
    if errors:
        raise HTTPException(status_code=400, detail={"code": "WEAK_PASSWORD", "message": "; ".join(errors)})

    # Загружаем историю и проверяем, не используется ли уже такой пароль
    hist_result = await db.execute(
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user.id)
        .order_by(desc(PasswordHistory.created_at))
        .limit(settings.PASSWORD_HISTORY_SIZE)
    )
    for hist in hist_result.scalars().all():
        if verify_password(body.new_password, hist.password_hash):
            raise HTTPException(status_code=400, detail={
                "code": "PASSWORD_REUSE",
                "message": f"Пароль уже использовался (последние {settings.PASSWORD_HISTORY_SIZE})",
            })

    # Перекладываем текущий хеш в историю перед заменой
    db.add(PasswordHistory(user_id=user.id, password_hash=user.password_hash))
    user.password_hash = hash_password(body.new_password)
    user.password_expires_at = (
        datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRY_DAYS)
    ).replace(tzinfo=None)

    audit = AuthAuditLogger(db)
    await audit.log(
        action="user.password_changed", resource_type="user", resource_id=str(user.id),
        user_id=user.id, request=request,
    )
    await db.commit()
    return {"message": "Пароль изменён"}


@router.post("/2fa/setup")
async def setup_2fa(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Первый этап настройки 2FA: генерация TOTP-секрета и резервных кодов.

    Устройство создаётся с is_active=False – активация происходит только после
    успешной проверки кода через /2fa/confirm. Это гарантирует, что пользователь
    правильно настроил приложение-аутентификатор перед включением 2FA.

    Секрет шифруется AES-256 (TOTP_ENCRYPTION_KEY) перед сохранением в БД.
    Резервные коды хешируются Argon2id – в БД хранятся только хеши.
    """
    import secrets
    user = (await db.execute(select(User).where(User.id == token.sub))).scalar_one_or_none()

    # Генерируем новый случайный BASE32 секрет (совместим с Google Authenticator и др.)
    secret = pyotp.random_base32()
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="ГОСТ34-Система")

    # 8 одноразовых резервных кодов длиной 8 символов (hex)
    backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]
    backup_hashes = [hash_password(code) for code in backup_codes]

    existing = (await db.execute(select(TotpDevice).where(TotpDevice.user_id == user.id))).scalar_one_or_none()
    if existing:
        # Перезаписываем существующее устройство – пользователь переинициализирует 2FA
        existing.secret_encrypted = encrypt_totp(secret)
        existing.backup_codes_hash = str(backup_hashes)
        existing.is_active = False  # Деактивируем до подтверждения
    else:
        db.add(TotpDevice(
            user_id=user.id,
            secret_encrypted=encrypt_totp(secret),
            backup_codes_hash=str(backup_hashes),
            is_active=False,
        ))
    await db.commit()

    # Возвращаем секрет и URI для QR-кода – клиент сканирует его в приложении
    # Резервные коды показываются пользователю один раз здесь; потом – только хеши в БД
    return {"secret": secret, "provisioning_uri": provisioning_uri, "backup_codes": backup_codes}


@router.post("/2fa/confirm")
async def confirm_2fa(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Второй этап настройки 2FA: подтверждение кодом из приложения.

    Активирует устройство только если TOTP-код верен. valid_window=1 допускает
    коды из соседних 30-секундных окон для компенсации небольшого рассинхрона часов.
    """
    from pydantic import BaseModel
    class ConfirmBody(BaseModel):
        code: str

    body = ConfirmBody(**(await request.json()))
    device = (await db.execute(select(TotpDevice).where(TotpDevice.user_id == token.sub))).scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=400, detail={"code": "NO_TOTP_DEVICE", "message": "Сначала вызовите /2fa/setup"})

    # Расшифровываем секрет из БД и проверяем код
    if not pyotp.TOTP(decrypt_totp(device.secret_encrypted)).verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail={"code": "INVALID_TOTP_CODE", "message": "Неверный код"})

    device.is_active = True
    await db.commit()
    return {"message": "2FA активирована"}


@router.delete("/2fa")
async def disable_2fa(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Отключение 2FA текущим пользователем.

    Запрещено, если для роли пользователя 2FA обязательна (is_2fa_required = True).
    Для подтверждения действия требуется ввод текущего пароля.
    """
    from pydantic import BaseModel
    class DisableBody(BaseModel):
        password: str

    body = DisableBody(**(await request.json()))
    user = (await db.execute(select(User).where(User.id == token.sub))).scalar_one_or_none()

    # is_2fa_required устанавливается администратором – пользователь не может его обойти
    if user.is_2fa_required:
        raise HTTPException(status_code=403, detail={"code": "2FA_REQUIRED_BY_ROLE", "message": "2FA обязательна для вашей роли"})

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail={"code": "INVALID_PASSWORD", "message": "Неверный пароль"})

    device = (await db.execute(select(TotpDevice).where(TotpDevice.user_id == user.id))).scalar_one_or_none()
    if device:
        await db.delete(device)
    await db.commit()
    return {"message": "2FA отключена"}


@router.get("/personal-data")
async def get_personal_data(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Выдача собственных персональных данных пользователю (право на доступ, 152-ФЗ).

    Каждое обращение записывается в аудит – это позволяет отследить,
    когда и кем запрашивалась выгрузка ПДн.
    Телефон расшифровывается из AES-256; если расшифровка не удалась – возвращается null.
    """
    from app.services.crypto import decrypt_phone
    user = (await db.execute(select(User).where(User.id == token.sub))).scalar_one_or_none()

    # Аудит доступа к ПДн – требование 152-ФЗ
    audit = AuthAuditLogger(db)
    await audit.log(
        action="user.personal_data_accessed", resource_type="user", resource_id=str(user.id),
        user_id=user.id, request=request,
    )
    await db.commit()

    phone = None
    if user.phone_encrypted:
        try:
            phone = decrypt_phone(user.phone_encrypted)
        except Exception:
            # Расшифровка может не удаться при ротации ключей – возвращаем null
            phone = None

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "position": user.position,
        "phone": phone,
        "organization_id": str(user.organization_id),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/deactivate")
async def request_deactivation(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Самостоятельная деактивация аккаунта пользователем (право на забвение, 152-ФЗ).

    MVP: анонимизация выполняется немедленно.
    Production: должна быть задержка 30 дней с возможностью отмены запроса.

    После анонимизации вход в систему невозможен – password_hash = "DEACTIVATED".
    """
    from pydantic import BaseModel
    class DeactivateBody(BaseModel):
        password: str

    body = DeactivateBody(**(await request.json()))
    user = (await db.execute(select(User).where(User.id == token.sub))).scalar_one_or_none()

    # Требуем подтверждение паролем – защита от случайного или несанкционированного удаления
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail={"code": "INVALID_PASSWORD", "message": "Неверный пароль"})

    audit = AuthAuditLogger(db)
    await audit.log(
        action="user.deactivation_requested", resource_type="user", resource_id=str(user.id),
        user_id=user.id, request=request,
    )
    # MVP: мгновенная анонимизация (production: запланировать через 30 дней)
    _anonymize_user(user)
    await db.commit()
    return {"message": "Аккаунт деактивирован и обезличен"}


def _anonymize_user(user: User) -> None:
    """
    Обезличивание данных пользователя для соответствия 152-ФЗ.

    После анонимизации:
    – ФИО заменяется на «Пользователь <первые 8 символов UUID>»
    – email заменяется на <UUID>@deactivated.local (уникален, не пересекается с реальными)
    – телефон обнуляется
    – хеш пароля заменяется маркером "DEACTIVATED" (verify_password вернёт False для любого пароля)
    – аккаунт деактивируется
    """
    short_id = str(user.id)[:8]
    user.full_name = f"Пользователь {short_id}"
    user.email = f"{user.id}@deactivated.local"
    user.phone_encrypted = None
    user.password_hash = "DEACTIVATED"
    user.is_active = False
