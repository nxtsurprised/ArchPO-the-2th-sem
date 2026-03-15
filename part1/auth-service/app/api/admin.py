from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from datetime import datetime

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, Project, Role, UserProjectRole
from app.models.session import Session
from app.models.audit import AuditLog
from app.schemas.user import UserCreate, UserResponse, RoleAssignment, UserRoleInfo
from app.schemas.audit import AuditLogResponse
from app.services.password import hash_password, validate_password_policy
from app.services.audit_service import AuthAuditLogger
from shared.schemas.user import TokenPayload
from shared.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/api/auth", tags=["admin"])


def _has_perm(token: TokenPayload, perm: str, project_id: UUID | None = None) -> bool:
    """
    Локальная проверка разрешения для роутеров admin.

    Суперадмин имеет все права автоматически. Остальные пользователи проверяются
    по набору permissions, закреплённых за ролью (admin или pm) в рамках проекта.
    Если project_id указан – проверяем только роли в этом проекте.

    Функция намеренно встроена в роутер (а не вынесена в shared), потому что
    это Auth-специфичная логика – права для других сервисов проверяются через
    /internal/users/{id}/permissions.
    """
    if token.is_superadmin:
        return True

    # Полный набор permissions, доступных роли admin
    ADMIN_PERMS = {"user.create", "user.deactivate", "user.assign_role", "user.reset_password",
                   "user.force_logout", "audit.view", "user.view_full_pdn"}
    # Урезанный набор для PM (руководитель проекта)
    PM_PERMS = {"user.assign_role", "audit.view"}

    for role in token.roles:
        # Если запрошена проверка в контексте конкретного проекта – пропускаем чужие роли
        if project_id and role.project_id != project_id:
            continue
        if role.role == "admin" and perm in ADMIN_PERMS:
            return True
        if role.role == "pm" and perm in PM_PERMS:
            return True
    return False


def _mask_email(email: str) -> str:
    """
    Частично скрывает email для пользователей без права user.view_full_pdn.

    Пример: john.doe@example.com → joh***@example.com
    Первые 3 символа локальной части сохраняются, остальное маскируется.
    """
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return local[:3] + "***@" + domain


def _mask_name(full_name: str) -> str:
    """
    Сокращает ФИО до формата «Фамилия И.О.» для частичного сокрытия ПДн.

    Пример: Иванов Иван Иванович → Иванов И.И.
    """
    parts = full_name.split()
    if len(parts) >= 2:
        initials = "".join(f"{p[0]}." for p in parts[1:])
        return f"{parts[0]} {initials}"
    return full_name


async def _build_user_roles(db: AsyncSession, user: User) -> list[UserRoleInfo]:
    """
    Собирает список ролей пользователя по всем проектам.

    Сторона (customer/contractor) вычисляется динамически: сравниваем organization_id
    пользователя с полями проекта. Это позволяет не хранить side в БД.
    """
    stmt = (
        select(UserProjectRole, Project, Role)
        .join(Project, UserProjectRole.project_id == Project.id)
        .join(Role, UserProjectRole.role_id == Role.id)
        .where(UserProjectRole.user_id == user.id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        UserRoleInfo(
            project_id=proj.id,
            project_name=proj.name,
            role=role.name,
            side="customer" if user.organization_id == proj.customer_org_id else "contractor",
        )
        for _, proj, role in rows
    ]


@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users(
    request: Request,
    project_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Список пользователей с опциональной фильтрацией по проекту.

    Пользователи без права user.view_full_pdn видят замаскированные email и ФИО –
    это защищает персональные данные от сотрудников с ограниченным доступом.
    """
    if not _has_perm(token, "audit.view"):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Недостаточно прав"})

    stmt = select(User)
    if project_id:
        # Фильтруем только пользователей, назначенных в указанный проект
        stmt = stmt.join(UserProjectRole, UserProjectRole.user_id == User.id).where(
            UserProjectRole.project_id == project_id
        )

    # Подсчёт общего числа записей через subquery, чтобы получить корректную пагинацию
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    users = (await db.execute(stmt.offset((page - 1) * per_page).limit(per_page))).scalars().all()

    # Показываем полные данные только тем, у кого есть right user.view_full_pdn
    show_full = _has_perm(token, "user.view_full_pdn")
    items = []
    for u in users:
        items.append(UserResponse(
            id=u.id,
            email=u.email if show_full else _mask_email(u.email),
            full_name=u.full_name if show_full else _mask_name(u.full_name),
            position=u.position,
            is_active=u.is_active,
            is_2fa_required=u.is_2fa_required,
            organization_id=u.organization_id,
            roles=await _build_user_roles(db, u),
            created_at=u.created_at,
        ))

    return PaginatedResponse(items=items, total=total, page=page, per_page=per_page)


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Создание нового пользователя.

    Обычный admin может создавать пользователей только своей организации.
    Суперадмин может создавать пользователей в любой организации (cross-org).
    """
    if not _has_perm(token, "user.create"):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Недостаточно прав"})

    # Защита от создания пользователей в чужой организации без прав суперадмина
    if not token.is_superadmin and body.organization_id != token.org_id:
        raise HTTPException(status_code=403, detail={
            "code": "FORBIDDEN_CROSS_ORG",
            "message": "Можно создавать пользователей только своей организации",
        })

    # Проверяем политику паролей до обращения к БД – fail fast
    errors = validate_password_policy(body.password, body.email, body.full_name)
    if errors:
        raise HTTPException(status_code=400, detail={"code": "WEAK_PASSWORD", "message": "; ".join(errors)})

    # Проверяем уникальность email
    if (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"code": "EMAIL_EXISTS", "message": "Email уже используется"})

    from datetime import datetime, timezone, timedelta
    from app.config import get_settings
    settings = get_settings()

    new_user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        position=body.position,
        organization_id=body.organization_id,
        # Пароль действует PASSWORD_EXPIRY_DAYS дней с момента создания
        password_expires_at=(
            datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRY_DAYS)
        ).replace(tzinfo=None),
    )
    db.add(new_user)

    audit = AuthAuditLogger(db)
    await audit.log(
        action="user.created", resource_type="user", resource_id=body.email,
        user_id=token.sub, request=request,
    )
    await db.commit()
    await db.refresh(new_user)  # Обновляем объект, чтобы получить server-side поля (id, created_at)

    return UserResponse(
        id=new_user.id, email=new_user.email, full_name=new_user.full_name,
        position=new_user.position, is_active=new_user.is_active,
        is_2fa_required=new_user.is_2fa_required, organization_id=new_user.organization_id,
        roles=[], created_at=new_user.created_at,
    )


@router.patch("/users/{user_id}/roles")
async def assign_role(
    user_id: UUID,
    body: RoleAssignment,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Назначение роли пользователю в проекте (upsert).

    Если запись user_project_role уже существует – обновляем роль.
    Если нет – создаём новую. Один пользователь имеет одну роль в проекте
    (UniqueConstraint user_id + project_id).
    """
    # Проверяем right user.assign_role в контексте конкретного проекта
    if not _has_perm(token, "user.assign_role", body.project_id):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Недостаточно прав"})

    role = (await db.execute(select(Role).where(Role.name == body.role_name))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail={"code": "ROLE_NOT_FOUND", "message": "Роль не найдена"})

    existing = (await db.execute(
        select(UserProjectRole).where(
            and_(UserProjectRole.user_id == user_id, UserProjectRole.project_id == body.project_id)
        )
    )).scalar_one_or_none()

    if existing:
        # Пользователь уже в проекте – просто меняем роль
        existing.role_id = role.id
        existing.assigned_by = token.sub
    else:
        # Первичное назначение в проект
        db.add(UserProjectRole(
            user_id=user_id, project_id=body.project_id, role_id=role.id, assigned_by=token.sub,
        ))

    audit = AuthAuditLogger(db)
    await audit.log(
        action="user.role_assigned", resource_type="user_project_role",
        # resource_id составной: user:project, что позволяет идентифицировать событие в аудите
        resource_id=f"{user_id}:{body.project_id}", user_id=token.sub,
        project_id=body.project_id, request=request,
    )
    await db.commit()
    return {"message": "Роль назначена"}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Деактивация пользователя (is_active = False).

    Деактивированный пользователь не может войти в систему (шаг 3 login_user),
    но его данные и история сохраняются. Для полного удаления ПДн – /me/deactivate.
    """
    if not _has_perm(token, "user.deactivate"):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Недостаточно прав"})

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Пользователь не найден"})

    # Обычный admin не может деактивировать пользователей другой организации
    if not token.is_superadmin and user.organization_id != token.org_id:
        raise HTTPException(status_code=403, detail={
            "code": "FORBIDDEN_CROSS_ORG", "message": "Нельзя деактивировать пользователя другой организации",
        })

    user.is_active = False
    audit = AuthAuditLogger(db)
    await audit.log(
        action="user.deactivated", resource_type="user", resource_id=str(user_id),
        user_id=token.sub, request=request,
    )
    await db.commit()
    return {"message": "Пользователь деактивирован"}


@router.post("/users/{user_id}/unlock")
async def unlock_user(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Снятие блокировки с аккаунта (ручная разблокировка после failed_login_attempts).

    Использует право user.reset_password, так как это административное действие
    над учётными данными (семантически близко к сбросу пароля).
    """
    if not _has_perm(token, "user.reset_password"):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Недостаточно прав"})

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Пользователь не найден"})

    # Сбрасываем счётчик и снимаем временную блокировку
    user.failed_login_attempts = 0
    user.locked_until = None

    audit = AuthAuditLogger(db)
    await audit.log(
        action="user.unlocked", resource_type="user", resource_id=str(user_id),
        user_id=token.sub, request=request,
    )
    await db.commit()
    return {"message": "Пользователь разблокирован"}


@router.post("/users/{user_id}/force-logout")
async def force_logout(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Принудительный выход пользователя со всех устройств.

    Отзывает все активные сессии: пользователь не сможет использовать
    существующие refresh-токены для получения новых access-токенов.
    Текущие access-токены продолжат работать до истечения (15 мин) –
    для немедленного отзыва потребовался бы blacklist (v2).
    """
    if not _has_perm(token, "user.force_logout"):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Недостаточно прав"})

    sessions = (await db.execute(
        select(Session).where(and_(Session.user_id == user_id, Session.is_revoked == False))
    )).scalars().all()

    for s in sessions:
        s.is_revoked = True

    audit = AuthAuditLogger(db)
    await audit.log(
        action="user.force_logout", resource_type="user", resource_id=str(user_id),
        user_id=token.sub, request=request,
    )
    await db.commit()
    return {"message": f"Завершено {len(sessions)} сессий"}


@router.get("/audit", response_model=PaginatedResponse[AuditLogResponse])
async def get_audit(
    request: Request,
    user_id: UUID | None = Query(None),
    action: str | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
):
    """
    Журнал аудита Auth Service с фильтрацией.

    Возвращает только события сервиса аутентификации.
    Для агрегированного аудита по всем сервисам используется /audit/unified (superadmin).
    Параметры alias="from"/"to" позволяют использовать зарезервированные слова как query-параметры.
    """
    if not _has_perm(token, "audit.view"):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Недостаточно прав"})

    stmt = select(AuditLog)
    filters = []
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if from_dt:
        filters.append(AuditLog.timestamp >= from_dt)
    if to_dt:
        filters.append(AuditLog.timestamp <= to_dt)
    if filters:
        stmt = stmt.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    # Сортируем по убыванию – самые последние события первыми
    entries = (await db.execute(
        stmt.order_by(desc(AuditLog.timestamp)).offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()

    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(e) for e in entries],
        total=total, page=page, per_page=per_page,
    )
