from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
import structlog
from sqlalchemy import select

logger = structlog.get_logger()

# ── Справочные данные ────────────────────────────────────────────────────────

# Три проектные роли с фиксированными UUID, чтобы seed был идемпотентным
# и можно было ссылаться на них в других местах (тестах, документации).
ROLES = [
    {"id": "11111111-0000-0000-0000-000000000001", "name": "pm", "display_name": "Руководитель проекта"},
    {"id": "11111111-0000-0000-0000-000000000002", "name": "admin", "display_name": "Администратор проекта"},
    {"id": "11111111-0000-0000-0000-000000000003", "name": "analyst", "display_name": "Аналитик"},
]

# Полный список 38 permission-кодов из матрицы прав (docs/permissions-matrix.md).
# Формат кортежа: (code, description, resource, action)
ALL_PERMISSIONS = [
    # Auth Service – управление пользователями и аудитом
    ("user.create", "Создание аккаунта", "user", "create"),
    ("user.deactivate", "Деактивация аккаунта", "user", "deactivate"),
    ("user.assign_role", "Назначение ролей", "user", "assign_role"),
    ("user.reset_password", "Сброс пароля", "user", "reset_password"),
    ("user.force_logout", "Принудительный выход", "user", "force_logout"),
    ("audit.view", "Просмотр журнала аудита", "audit", "view"),
    ("audit.view_unified", "Агрегированный аудит", "audit", "view_unified"),
    ("user.view_full_pdn", "Просмотр полных ПДн", "user", "view_full_pdn"),
    # Catalog – подсистемы
    ("subsystem.view", "Просмотр подсистем", "subsystem", "view"),
    ("subsystem.create", "Создание подсистем", "subsystem", "create"),
    ("subsystem.edit", "Редактирование подсистем", "subsystem", "edit"),
    ("subsystem.delete", "Удаление подсистем", "subsystem", "delete"),
    ("subsystem.reorder", "Изменение порядка подсистем", "subsystem", "reorder"),
    # Catalog – функции
    ("function.view", "Просмотр функций", "function", "view"),
    ("function.create", "Создание функций", "function", "create"),
    ("function.edit_info", "Редактирование описания функций", "function", "edit_info"),
    ("function.edit_cost", "Редактирование стоимости", "function", "edit_cost"),
    ("function.edit_priority", "Изменение приоритета", "function", "edit_priority"),
    ("function.move", "Перенос функций", "function", "move"),
    ("function.delete", "Удаление функций", "function", "delete"),
    # Catalog – ставки
    ("rates.view", "Просмотр ставок", "rates", "view"),
    ("rates.edit", "Изменение ставок", "rates", "edit"),
    # Catalog – шаблоны
    ("template.view", "Просмотр шаблонов", "template", "view"),
    ("template.create", "Создание шаблонов", "template", "create"),
    ("template.edit", "Редактирование шаблонов", "template", "edit"),
    ("template.delete", "Удаление шаблонов", "template", "delete"),
    # Catalog – документы
    ("document.view", "Просмотр документов", "document", "view"),
    ("document.create", "Создание документов", "document", "create"),
    ("document.edit", "Редактирование документов", "document", "edit"),
    ("document.delete", "Удаление документов", "document", "delete"),
    # Workflow – согласование
    ("approval.submit", "Отправить на согласование", "approval", "submit"),
    ("approval.decide_tz", "Финальное решение по ТЗ", "approval", "decide_tz"),
    ("approval.decide_nmck", "Финальное решение по НМЦК", "approval", "decide_nmck"),
    ("approval.review", "Рецензия", "approval", "review"),
    ("approval.revoke", "Отзыв решения", "approval", "revoke"),
    ("approval.cancel", "Отмена согласования", "approval", "cancel"),
    ("approval.view", "Просмотр согласований", "approval", "view"),
    ("approval.view_history", "История раундов", "approval", "view_history"),
]

# Матрица прав: какие permission-коды доступны каждой роли.
# Соответствует docs/permissions-matrix.md (38 permissions × 7 ролей –
# здесь только 3 роли; 2 стороны × 3 роли = 6 контекстных ролей + суперадмин).
ROLE_PERMISSIONS = {
    "pm": [
        # PM управляет составом команды и видит аудит
        "user.assign_role", "audit.view",
        # Полный контроль над каталогом
        "subsystem.view", "subsystem.create", "subsystem.edit", "subsystem.delete", "subsystem.reorder",
        "function.view", "function.create", "function.edit_info", "function.edit_cost",
        "function.edit_priority", "function.move", "function.delete",
        "rates.view", "rates.edit",
        "template.view", "template.create", "template.edit", "template.delete",
        "document.view", "document.create", "document.edit", "document.delete",
        # Все действия с согласованием, включая финальные решения
        "approval.submit", "approval.decide_tz", "approval.decide_nmck",
        "approval.review", "approval.revoke", "approval.cancel",
        "approval.view", "approval.view_history",
    ],
    "admin": [
        # Admin управляет пользователями своей организации
        "user.create", "user.deactivate", "user.assign_role", "user.reset_password",
        "user.force_logout", "audit.view", "user.view_full_pdn",
        # Только просмотр каталога (не редактирование)
        "subsystem.view", "function.view", "rates.view",
        "template.view", "template.create", "template.edit",
        "document.view", "document.create", "document.edit",
        # Ограниченное участие в согласовании (без финальных решений)
        "approval.submit", "approval.cancel", "approval.view", "approval.view_history",
    ],
    "analyst": [
        # Analyst работает с функциями и подсистемами, участвует в рецензировании
        "subsystem.view", "subsystem.create", "subsystem.edit",
        "function.view", "function.create", "function.edit_info",
        "rates.view", "template.view", "document.view", "document.edit",
        "approval.submit", "approval.review", "approval.view", "approval.view_history",
    ],
}


async def seed_all() -> None:
    """
    Заполнение справочников начальными данными (идемпотентный запуск).

    Порядок важен из-за внешних ключей:
    1. Роли
    2. Права (permissions)
    3. Привязка прав к ролям (role_permissions)
    4. Организации
    5. Суперадмин (требует существующей организации)
    6. Тестовый проект (требует двух организаций)

    Каждая секция использует select-before-insert для идемпотентности –
    повторный запуск не создаёт дубликатов.
    """
    from app.database import get_session_factory
    from app.models.user import Role, Permission, RolePermission, Organization, User, Project
    from app.services.password import hash_password

    factory = get_session_factory()

    async with factory() as db:
        # ── Шаг 1: Роли ─────────────────────────────────────────────────────
        for rd in ROLES:
            if not (await db.execute(select(Role).where(Role.name == rd["name"]))).scalar_one_or_none():
                db.add(Role(id=uuid.UUID(rd["id"]), name=rd["name"], display_name=rd["display_name"]))
        await db.flush()

        # ── Шаг 2: Права (permissions) ──────────────────────────────────────
        # perm_map нужен на шаге 3 для создания role_permissions без дополнительных запросов
        perm_map: dict[str, uuid.UUID] = {}
        for code, desc, resource, action in ALL_PERMISSIONS:
            perm = (await db.execute(select(Permission).where(Permission.code == code))).scalar_one_or_none()
            if not perm:
                perm = Permission(id=uuid.uuid4(), code=code, description=desc, resource=resource, action=action)
                db.add(perm)
                await db.flush()  # flush сразу, чтобы perm.id был доступен ниже
            perm_map[code] = perm.id
        await db.flush()

        # ── Шаг 3: Привязка прав к ролям ────────────────────────────────────
        for rd in ROLES:
            role = (await db.execute(select(Role).where(Role.name == rd["name"]))).scalar_one()
            for perm_code in ROLE_PERMISSIONS.get(rd["name"], []):
                perm_id = perm_map.get(perm_code)
                if not perm_id:
                    continue
                # Проверяем существование связи перед добавлением
                if not (await db.execute(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id, RolePermission.permission_id == perm_id,
                    )
                )).scalar_one_or_none():
                    db.add(RolePermission(role_id=role.id, permission_id=perm_id))
        await db.flush()

        # ── Шаг 4: Организации ───────────────────────────────────────────────
        # Фиксированные UUID позволяют ссылаться на организации в тестах
        minstroy_id = uuid.UUID("22222222-0000-0000-0000-000000000001")
        softdev_id = uuid.UUID("22222222-0000-0000-0000-000000000002")

        if not (await db.execute(select(Organization).where(Organization.inn == "7707074507"))).scalar_one_or_none():
            db.add(Organization(
                id=minstroy_id, name="Минстрой России", inn="7707074507",
                legal_address="г. Москва, ул. Садовая-Самотёчная, д. 10/23, стр. 1",
            ))

        if not (await db.execute(select(Organization).where(Organization.inn == "7712345678"))).scalar_one_or_none():
            db.add(Organization(id=softdev_id, name="ООО СофтДев", inn="7712345678"))
        await db.flush()

        # ── Шаг 5: Суперадмин ────────────────────────────────────────────────
        # Пароль "changeme" – должен быть сменён при первом входе в production
        if not (await db.execute(select(User).where(User.email == "admin@system.local"))).scalar_one_or_none():
            db.add(User(
                id=uuid.UUID("33333333-0000-0000-0000-000000000001"),
                organization_id=minstroy_id,
                email="admin@system.local",
                password_hash=hash_password("changeme"),
                full_name="Системный Администратор",
                position="Суперадминистратор",
                is_superadmin=True,
                # Срок действия пароля – 90 дней с момента создания
                password_expires_at=(
                    datetime.now(timezone.utc) + timedelta(days=90)
                ).replace(tzinfo=None),
            ))

        # ── Шаг 6: Тестовый проект ───────────────────────────────────────────
        # Минстрой – заказчик, ООО СофтДев – подрядчик
        if not (await db.execute(select(Project).where(Project.code == "GIS-ZKH"))).scalar_one_or_none():
            db.add(Project(
                id=uuid.UUID("44444444-0000-0000-0000-000000000001"),
                name="ГИС ЖКХ",
                code="GIS-ZKH",
                description="Государственная информационная система жилищно-коммунального хозяйства",
                customer_org_id=minstroy_id,
                contractor_org_id=softdev_id,
            ))

        # Единый commit в конце – либо всё сохраняется, либо ничего
        await db.commit()
        logger.info("seeds_completed")
