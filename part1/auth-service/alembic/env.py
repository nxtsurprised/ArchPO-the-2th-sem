from __future__ import annotations
import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Объект конфигурации Alembic – предоставляет доступ к значениям из alembic.ini
config = context.config

# Настраиваем стандартный logging Python по конфигу из alembic.ini,
# если файл конфигурации существует (не передан как None при программном вызове)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Читаем параметры подключения к БД из переменных окружения.
# Это позволяет использовать одни и те же миграции в dev/staging/production
# без изменения файлов в репозитории.
DB_USER = os.getenv("DB_USER", "auth_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "auth_secret")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "auth_db")

# Перезаписываем sqlalchemy.url из alembic.ini значением из окружения
config.set_main_option(
    "sqlalchemy.url",
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

# Импортируем Base и все модели, чтобы Alembic видел метаданные таблиц
# при автогенерации миграций (alembic revision --autogenerate).
# Импорт app.models гарантирует регистрацию всех submodules в Base.metadata.
from app.database import Base
import app.models  # noqa: F401 – side-effect import, нужен для регистрации моделей

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Offline-режим: генерация SQL без подключения к БД.

    Используется для предварительного просмотра миграций или генерации
    SQL-скрипта для ручного применения DBA.
    literal_binds=True – значения параметров встраиваются в SQL строки, а не как placeholders.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """
    Синхронная обёртка для применения миграций через существующее соединение.

    Вызывается из run_async_migrations через connection.run_sync(), что позволяет
    использовать синхронный API Alembic с асинхронным движком SQLAlchemy.
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Создаёт асинхронный движок и применяет миграции.

    NullPool используется в миграциях, чтобы не держать постоянный пул соединений –
    миграции запускаются один раз при старте сервиса.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        # run_sync позволяет вызвать синхронную функцию do_run_migrations
        # внутри async-контекста
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Точка входа для online-режима: запускает async-миграции через asyncio."""
    asyncio.run(run_async_migrations())


# Alembic вызывает этот модуль напрямую – выбираем режим по флагу контекста
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
