from __future__ import annotations
import uuid
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, String, Integer,
    Text, UniqueConstraint, CheckConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Organization(Base):
    """
    Организация – заказчик или подрядчик.

    Важно: организация сама по себе нейтральна. Её роль (customer / contractor)
    определяется через поля проекта: Project.customer_org_id и contractor_org_id.
    Один и тот же юрлик может быть заказчиком в одном проекте
    и подрядчиком в другом.
    """
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    inn = Column(String(12), unique=True, nullable=False)   # уникальный идентификатор юрлица
    ogrn = Column(String(15), unique=True)
    legal_address = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    users = relationship("User", back_populates="organization")


class User(Base):
    """
    Пользователь системы.

    Персональные данные (телефон) хранятся в зашифрованном виде (AES-256 Fernet).
    Пароль хранится только как Argon2id-хеш – восстановление невозможно.

    failed_login_attempts + locked_until реализуют блокировку после 5 неудачных входов.
    password_expires_at – дата, после которой система требует смену пароля.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone_encrypted = Column(Text)            # AES-256 (Fernet, ключ ENCRYPT_KEY_PHONE)
    password_hash = Column(Text, nullable=False)  # Argon2id
    full_name = Column(String(255), nullable=False)
    position = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superadmin = Column(Boolean, default=False)  # надпроектный флаг
    is_2fa_required = Column(Boolean, default=False)  # если True – вход без TOTP невозможен
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)           # NULL – не заблокирован
    password_expires_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="users")
    sessions = relationship("Session", back_populates="user")
    # foreign_keys указан явно, так как UserProjectRole имеет два FK на users
    project_roles = relationship("UserProjectRole", back_populates="user", foreign_keys="UserProjectRole.user_id")
    totp_devices = relationship("TotpDevice", back_populates="user")
    password_history = relationship("PasswordHistory", back_populates="user")
    consent_records = relationship("ConsentRecord", back_populates="user")


class Project(Base):
    """
    Проект – основная единица работы в системе.

    Связывает двух участников: заказчика (customer_org) и подрядчика (contractor_org).
    CHECK-ограничение different_sides на уровне БД гарантирует, что одна организация
    не может быть одновременно заказчиком и подрядчиком в одном проекте.

    status: active (в работе) / archived (завершён).
    """
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("customer_org_id != contractor_org_id", name="different_sides"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)  # короткий буквенный код, напр. "GIS-ZKH"
    description = Column(Text)
    customer_org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    contractor_org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, server_default=func.now())

    # Два отдельных relationship на одну таблицу – нужен явный foreign_keys
    customer_org = relationship("Organization", foreign_keys=[customer_org_id])
    contractor_org = relationship("Organization", foreign_keys=[contractor_org_id])
    user_roles = relationship("UserProjectRole", back_populates="project")


class Role(Base):
    """
    Справочник ролей: pm, admin, analyst.

    Роли проектные – они не хранят сторону (side), потому что одна организация
    может быть заказчиком в одном проекте и подрядчиком в другом.
    Сторона вычисляется динамически через Project.customer_org_id / contractor_org_id.
    """
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)           # "pm", "admin", "analyst"
    display_name = Column(String(100), nullable=False)  # "Руководитель проекта"

    role_permissions = relationship("RolePermission", back_populates="role")
    user_project_roles = relationship("UserProjectRole", back_populates="role")


class Permission(Base):
    """
    Атомарное право доступа, например "function.edit_cost".

    code = resource + "." + action – по этой строке сервисы проверяют доступ.
    Всего в системе 38 permissions (8 Auth + 22 Catalog + 8 Workflow).
    """
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, nullable=False)  # "function.edit_cost"
    description = Column(Text)
    resource = Column(String(50))   # "function"
    action = Column(String(50))     # "edit_cost"

    role_permissions = relationship("RolePermission", back_populates="permission")


class RolePermission(Base):
    """
    Связь многие-ко-многим: роль – разрешение.
    Заполняется seed-скриптом по матрице прав из docs/permissions-matrix.md.
    """
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True)

    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")


class UserProjectRole(Base):
    """
    Назначение роли пользователю в рамках конкретного проекта.

    UNIQUE(user_id, project_id) – один пользователь имеет ровно одну роль в проекте.
    Если нужно переназначить роль, запись обновляется, а не добавляется новая.

    assigned_by – UUID пользователя, который назначил роль (для аудита).
    """
    __tablename__ = "user_project_roles"
    __table_args__ = (UniqueConstraint("user_id", "project_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    assigned_at = Column(DateTime, server_default=func.now())
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))  # nullable – при первоначальном сиде

    # foreign_keys нужен SQLAlchemy, так как user_id и assigned_by оба FK на users
    user = relationship("User", back_populates="project_roles", foreign_keys=[user_id])
    project = relationship("Project", back_populates="user_roles")
    role = relationship("Role", back_populates="user_project_roles")
