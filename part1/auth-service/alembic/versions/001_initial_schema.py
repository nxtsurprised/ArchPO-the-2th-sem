"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-15
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None   # Первая миграция – нет предшественника
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations ────────────────────────────────────────────────────────
    # Организации-участники контрактов: заказчики и подрядчики.
    # ИНН уникален по закону – используется как бизнес-ключ.
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('inn', sa.String(12), nullable=False),
        sa.Column('ogrn', sa.String(15)),
        sa.Column('legal_address', sa.Text()),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inn'),
        sa.UniqueConstraint('ogrn'),
    )

    # ── users ────────────────────────────────────────────────────────────────
    # Пользователи системы. phone_encrypted – AES-256 (152-ФЗ).
    # failed_login_attempts и locked_until – для прогрессивной задержки и блокировки.
    # password_expires_at – пароль действует PASSWORD_EXPIRY_DAYS дней.
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone_encrypted', sa.Text()),               # AES-256, null если не указан
        sa.Column('password_hash', sa.Text(), nullable=False),  # Argon2id или маркер "DEACTIVATED"
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('position', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('is_superadmin', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('is_2fa_required', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('failed_login_attempts', sa.Integer(), server_default=sa.text('0')),
        sa.Column('locked_until', sa.DateTime()),              # null = не заблокирован
        sa.Column('password_expires_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    # ── projects ─────────────────────────────────────────────────────────────
    # Контракты/проекты. CheckConstraint гарантирует, что заказчик и подрядчик
    # разные организации – это фундаментальное бизнес-правило двустороннего контракта.
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),     # уникальный бизнес-код, напр. "GIS-ZKH"
        sa.Column('description', sa.Text()),
        sa.Column('customer_org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('contractor_org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), server_default=sa.text("'active'")),  # active | archived
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.CheckConstraint('customer_org_id != contractor_org_id', name='different_sides'),
        sa.ForeignKeyConstraint(['customer_org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['contractor_org_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    # ── roles ────────────────────────────────────────────────────────────────
    # Справочник проектных ролей: pm, admin, analyst.
    # UUID фиксированы в seed – роли не создаются динамически.
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── permissions ──────────────────────────────────────────────────────────
    # Справочник атомарных прав (38 permissions по матрице).
    # resource + action – дополнительная структуризация для поиска и группировки.
    op.create_table(
        'permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),    # напр. "document.edit"
        sa.Column('description', sa.Text()),
        sa.Column('resource', sa.String(50)),                  # напр. "document"
        sa.Column('action', sa.String(50)),                    # напр. "edit"
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    # ── role_permissions ─────────────────────────────────────────────────────
    # Связь многие-ко-многим: какие права есть у каждой роли.
    # Составной PK (role_id, permission_id) обеспечивает уникальность пар.
    op.create_table(
        'role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id']),
        sa.PrimaryKeyConstraint('role_id', 'permission_id'),
    )

    # ── user_project_roles ───────────────────────────────────────────────────
    # Назначения пользователей в проекты с указанием роли.
    # UniqueConstraint (user_id, project_id) – один пользователь, одна роль в проекте.
    # assigned_by – кто назначил (для аудита), может быть null для seed-записей.
    op.create_table(
        'user_project_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True)),  # null допускается (seed)
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'project_id'),
    )

    # ── sessions ─────────────────────────────────────────────────────────────
    # Сессии пользователей. В БД хранится только SHA-256 хеш refresh-токена –
    # оригинальный токен недоступен даже при компрометации БД.
    # ip_address – IPv4 (max 15) или IPv6 (max 45) символов.
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('refresh_token_hash', sa.String(255), nullable=False),  # SHA-256 hex (64 символа)
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── totp_devices ─────────────────────────────────────────────────────────
    # TOTP-устройства для двухфакторной аутентификации.
    # secret_encrypted – AES-256 шифрование TOTP-секрета (TOTP_ENCRYPTION_KEY).
    # is_active = False после /setup; True только после успешного /confirm.
    op.create_table(
        'totp_devices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('secret_encrypted', sa.Text(), nullable=False),
        sa.Column('backup_codes_hash', sa.Text()),  # JSON-список Argon2id хешей резервных кодов
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── password_history ─────────────────────────────────────────────────────
    # История паролей для предотвращения повторного использования.
    # Хранятся только хеши (Argon2id), не оригинальные пароли.
    op.create_table(
        'password_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── consent_records ──────────────────────────────────────────────────────
    # Журнал согласий на обработку персональных данных (152-ФЗ).
    # revoked_at – момент отзыва согласия (null = не отозвано).
    op.create_table(
        'consent_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('purpose', sa.String(100), nullable=False),  # цель обработки ПДн
        sa.Column('granted_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('revoked_at', sa.DateTime()),
        sa.Column('ip_address', sa.String(45)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── audit_log ────────────────────────────────────────────────────────────
    # Журнал аудита – append-only таблица (приложение имеет только INSERT).
    # JSONB для changes/details позволяет хранить структурированный контекст
    # без изменения схемы при добавлении новых типов событий.
    # Три индекса покрывают основные сценарии: поиск по проекту, по пользователю, по ресурсу.
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_side', sa.String(20)),       # customer | contractor | null (системные операции)
        sa.Column('user_role', sa.String(20)),        # pm | admin | analyst | null
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text()),
        sa.Column('service', sa.String(20), server_default=sa.text("'auth'")),  # auth | catalog | workflow
        sa.Column('action', sa.String(100), nullable=False),    # напр. "login.success"
        sa.Column('resource_type', sa.String(50), nullable=False),  # напр. "user"
        sa.Column('resource_id', sa.String(100), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True)),  # null для надпроектных операций
        sa.Column('correlation_id', sa.String(100)),             # X-Request-ID для трассировки
        sa.Column('result', sa.String(20), server_default=sa.text("'success'")),  # success|failure|denied
        sa.Column('changes', postgresql.JSONB()),   # { field: { old: ..., new: ... } }
        sa.Column('details', postgresql.JSONB()),   # произвольный контекст события
        sa.PrimaryKeyConstraint('id'),
    )
    # Составные индексы (поле + время) оптимизированы для пагинированных запросов
    # вида "события по проекту X за последний месяц, страница 3"
    op.create_index('idx_audit_project_time', 'audit_log', ['project_id', 'timestamp'])
    op.create_index('idx_audit_user_time', 'audit_log', ['user_id', 'timestamp'])
    op.create_index('idx_audit_resource', 'audit_log', ['resource_id', 'timestamp'])


def downgrade() -> None:
    # Удаляем в обратном порядке относительно upgrade – сначала зависимые таблицы
    op.drop_index('idx_audit_resource', table_name='audit_log')
    op.drop_index('idx_audit_user_time', table_name='audit_log')
    op.drop_index('idx_audit_project_time', table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_table('consent_records')
    op.drop_table('password_history')
    op.drop_table('totp_devices')
    op.drop_table('sessions')
    op.drop_table('user_project_roles')
    op.drop_table('role_permissions')
    op.drop_table('permissions')
    op.drop_table('roles')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('organizations')
