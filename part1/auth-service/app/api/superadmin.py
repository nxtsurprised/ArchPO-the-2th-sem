from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime

from app.database import get_db
from app.api.deps import require_superadmin
from app.models.user import Organization, Project
from app.models.audit import AuditLog
from app.schemas.user import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse,
    ProjectCreate, ProjectUpdate, ProjectResponse,
)
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import AuthAuditLogger
from shared.schemas.user import TokenPayload
from shared.schemas.pagination import PaginatedResponse

# Все роутеры этого модуля требуют глобального флага is_superadmin –
# проверка выполняется через Depends(require_superadmin) на каждом эндпоинте.
router = APIRouter(prefix="/api/auth", tags=["superadmin"])


@router.get("/organizations", response_model=PaginatedResponse[OrganizationResponse])
async def list_orgs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """Список всех организаций в системе (только суперадмин)."""
    total = (await db.execute(select(func.count()).select_from(Organization))).scalar_one()
    orgs = (await db.execute(
        select(Organization).offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    return PaginatedResponse(
        items=[OrganizationResponse.model_validate(o) for o in orgs],
        total=total, page=page, per_page=per_page,
    )


@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
async def create_org(
    body: OrganizationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """
    Регистрация новой организации (заказчика или подрядчика).

    ИНН уникален – это естественный бизнес-ключ организации.
    """
    org = Organization(**body.model_dump())
    db.add(org)
    audit = AuthAuditLogger(db)
    await audit.log(
        action="org.created", resource_type="organization", resource_id=body.inn, user_id=token.sub, request=request,
    )
    await db.commit()
    await db.refresh(org)
    return OrganizationResponse.model_validate(org)


@router.put("/organizations/{org_id}", response_model=OrganizationResponse)
async def update_org(
    org_id: UUID,
    body: OrganizationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """Обновление реквизитов организации (частичное – только переданные поля)."""
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail={"code": "ORG_NOT_FOUND", "message": "Организация не найдена"})
    # exclude_none=True – не перезаписываем поля, которые не были переданы в теле запроса
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(org, field, val)
    await db.commit()
    await db.refresh(org)
    return OrganizationResponse.model_validate(org)


@router.get("/projects", response_model=PaginatedResponse[ProjectResponse])
async def list_projects(
    org_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """
    Список всех проектов с опциональной фильтрацией по организации.

    Фильтр по org_id ищет организацию и в customer_org_id, и в contractor_org_id,
    потому что одна организация может участвовать в проектах с обеих сторон.
    """
    stmt = select(Project)
    if org_id:
        stmt = stmt.where(
            (Project.customer_org_id == org_id) | (Project.contractor_org_id == org_id)
        )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    projects = (await db.execute(stmt.offset((page - 1) * per_page).limit(per_page))).scalars().all()
    return PaginatedResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total, page=page, per_page=per_page,
    )


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """
    Создание нового проекта.

    CheckConstraint на уровне БД гарантирует, что customer_org_id != contractor_org_id
    (организация не может быть одновременно заказчиком и подрядчиком одного проекта).
    """
    project = Project(**body.model_dump())
    db.add(project)
    audit = AuthAuditLogger(db)
    await audit.log(
        action="project.created", resource_type="project", resource_id=body.code,
        user_id=token.sub, request=request,
    )
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """Обновление параметров проекта (частичное – только переданные поля)."""
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Проект не найден"})
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(project, field, val)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/archive")
async def archive_project(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """
    Архивирование проекта (мягкое закрытие).

    Переводит статус в 'archived' – проект перестаёт быть активным,
    но все данные и история сохраняются. Физическое удаление не предусмотрено.
    """
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Проект не найден"})
    project.status = "archived"
    await db.commit()
    return {"message": "Проект архивирован"}


@router.get("/audit/unified", response_model=PaginatedResponse[AuditLogResponse])
async def unified_audit(
    project_id: UUID | None = Query(None),
    user_id: UUID | None = Query(None),
    service: str | None = Query(None),
    action: str | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """
    Агрегированный аудит по всем сервисам (только суперадмин).

    В v1 Auth Service хранит только собственный аудит; другие сервисы пишут в свои БД
    и отдают события через /internal/audit. Поле service позволяет различать источники.
    В v2 – единый Audit Service через Kafka.
    """
    stmt = select(AuditLog)
    filters = []
    if project_id:
        filters.append(AuditLog.project_id == project_id)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if service:
        filters.append(AuditLog.service == service)
    if action:
        filters.append(AuditLog.action == action)
    if from_dt:
        filters.append(AuditLog.timestamp >= from_dt)
    if to_dt:
        filters.append(AuditLog.timestamp <= to_dt)
    if filters:
        stmt = stmt.where(and_(*filters))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    entries = (await db.execute(
        stmt.order_by(desc(AuditLog.timestamp)).offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()

    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(e) for e in entries],
        total=total, page=page, per_page=per_page,
    )


@router.get("/audit/resource/{resource_id}/timeline")
async def resource_timeline(
    resource_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """
    Хронологическая лента событий по конкретному ресурсу (документ, пользователь, проект).

    Сортировка по возрастанию времени – показывает историю ресурса от создания до текущего состояния.
    Используется для расследования инцидентов или разрешения конфликтных ситуаций.
    """
    stmt = select(AuditLog).where(AuditLog.resource_id == resource_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    entries = (await db.execute(
        # Хронология: события в порядке возникновения (ASC)
        stmt.order_by(AuditLog.timestamp).offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(e) for e in entries],
        total=total, page=page, per_page=per_page,
    )


@router.get("/audit/user/{user_id}/activity")
async def user_activity(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(require_superadmin),
):
    """
    Лента действий конкретного пользователя (активность).

    Сортировка по убыванию времени – последние действия первыми.
    Позволяет быстро понять, что делал пользователь в последнее время.
    """
    stmt = select(AuditLog).where(AuditLog.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    entries = (await db.execute(
        stmt.order_by(desc(AuditLog.timestamp)).offset((page - 1) * per_page).limit(per_page)
    )).scalars().all()
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(e) for e in entries],
        total=total, page=page, per_page=per_page,
    )
