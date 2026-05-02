from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from datetime import datetime

from app.database import get_db
from app.models.user import User, Organization, UserProjectRole, Role, Permission, RolePermission
from app.models.audit import AuditLog
from app.services.jwt_service import get_jwks
from app.config import get_settings
from shared.schemas.user import UserInfo

# Внутренние эндпоинты не маршрутизируются через nginx во внешнюю сеть –
# блок location /internal/ в nginx.conf закрыт для внешних запросов.
# Дополнительная защита – заголовок X-Internal-Secret.
router = APIRouter(tags=["internal"])


async def verify_internal_secret(x_internal_secret: str | None = Header(default=None)):
    """
    Проверка секретного ключа для внутренних вызовов между сервисами.

    Все сервисы при межсервисных запросах передают X-Internal-Secret.
    Значение задаётся через переменную окружения INTERNAL_API_SECRET и
    должно быть одинаковым для всех сервисов в одном окружении.
    """
    if x_internal_secret != get_settings().INTERNAL_API_SECRET:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Invalid internal secret"})


@router.get("/.well-known/jwks.json")
async def jwks():
    """
    JWKS-эндпоинт (JSON Web Key Set) для проверки подписи JWT другими сервисами.

    Публичный – доступен без аутентификации, т.к. содержит только открытый ключ.
    Другие сервисы кешируют ответ на 1 час (CacheService) и используют ключ
    для верификации RS256-токенов без обращения к Auth Service при каждом запросе.
    Соответствует RFC 7517.
    """
    try:
        return get_jwks()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "JWKS_ERROR", "message": str(e)})


@router.get("/internal/users/{user_id}", response_model=UserInfo, dependencies=[Depends(verify_internal_secret)])
async def get_user_info(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Получение базовой информации о пользователе для других сервисов.

    Используется Catalog, Generation и Workflow сервисами для получения
    ФИО, должности и названия организации без прямого доступа к БД Auth Service.
    """
    row = (await db.execute(
        select(User, Organization)
        .join(Organization, User.organization_id == Organization.id)
        .where(User.id == user_id)
    )).one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Пользователь не найден"})

    user, org = row
    # org_side здесь всегда "customer" – в MVP сторона определяется контекстом проекта,
    # а не организацией. Корректное значение side доступно через JWT roles.
    return UserInfo(id=user.id, full_name=user.full_name, position=user.position, org_name=org.name, org_side="customer")


@router.post("/internal/users/batch", dependencies=[Depends(verify_internal_secret)])
async def batch_get_users(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Пакетный запрос информации о нескольких пользователях за один вызов.

    Используется, например, Workflow Service при загрузке списка участников согласования,
    чтобы избежать N отдельных запросов к Auth Service.
    Принимает { "user_ids": ["uuid1", "uuid2", ...] } и возвращает словарь id → данные.
    """
    body = await request.json()
    user_ids = [UUID(uid) for uid in body.get("user_ids", [])]

    rows = (await db.execute(
        select(User, Organization)
        .join(Organization, User.organization_id == Organization.id)
        .where(User.id.in_(user_ids))
    )).all()

    # Возвращаем словарь для O(1) доступа по ID на стороне вызывающего сервиса
    return {
        "users": {
            str(u.id): {"id": str(u.id), "full_name": u.full_name, "position": u.position, "org_name": org.name}
            for u, org in rows
        }
    }


@router.get("/internal/users/{user_id}/permissions", dependencies=[Depends(verify_internal_secret)])
async def get_user_permissions(
    user_id: UUID,
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Список permission-кодов пользователя в конкретном проекте.

    Используется Catalog и Workflow сервисами для проверки прав при выполнении
    бизнес-операций (создание документа, отправка на согласование и т.д.).
    Если у пользователя нет роли в проекте – возвращаем пустой список.
    """
    row = (await db.execute(
        select(UserProjectRole, Role)
        .join(Role, UserProjectRole.role_id == Role.id)
        .where(and_(UserProjectRole.user_id == user_id, UserProjectRole.project_id == project_id))
    )).one_or_none()

    if not row:
        # Пользователь не назначен в проект – нет ни роли, ни прав
        return {"role": None, "permissions": []}

    upr, role = row
    # Загружаем все permission-коды, привязанные к роли через role_permissions
    permissions = (await db.execute(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
    )).scalars().all()

    return {"role": role.name, "permissions": [p.code for p in permissions]}


@router.get("/internal/audit", dependencies=[Depends(verify_internal_secret)])
async def internal_audit(
    user_id: UUID | None = Query(None),
    project_id: UUID | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    """
    Выдача аудит-событий Auth Service другим сервисам (для агрегации).

    Лимит 1000 записей за запрос – это внутренний эндпоинт для сервис-to-сервис
    коммуникации, не предназначенный для пагинации. В v2 заменяется стримингом через Kafka.
    """
    stmt = select(AuditLog)
    filters = []
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if project_id:
        filters.append(AuditLog.project_id == project_id)
    if from_dt:
        filters.append(AuditLog.timestamp >= from_dt)
    if to_dt:
        filters.append(AuditLog.timestamp <= to_dt)
    if filters:
        stmt = stmt.where(and_(*filters))

    entries = (await db.execute(stmt.order_by(desc(AuditLog.timestamp)).limit(1000))).scalars().all()
    return {
        "items": [
            {
                "id": str(e.id), "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "user_id": str(e.user_id), "action": e.action,
                "resource_type": e.resource_type, "resource_id": e.resource_id, "result": e.result,
            }
            for e in entries
        ]
    }
