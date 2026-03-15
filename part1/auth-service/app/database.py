from __future__ import annotations
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings


class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy-моделей сервиса."""
    pass


# Синглтоны – создаются один раз при первом обращении
_engine = None
_session_factory = None


def get_engine():
    """
    Возвращает asyncpg-движок (lazy singleton).

    pool_pre_ping=True – перед выдачей соединения из пула делает SELECT 1,
    чтобы обнаружить оборванные соединения после перезапуска PostgreSQL.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,   # проверяем живость соединения перед использованием
            pool_size=10,         # базовый размер пула
            max_overflow=20,      # дополнительные соединения при пиковой нагрузке
        )
    return _engine


def get_session_factory():
    """Возвращает фабрику сессий (lazy singleton)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # не инвалидируем объекты после commit – удобно для return после flush
        )
    return _session_factory


async def get_db():
    """
    FastAPI Dependency – инжектирует сессию БД в роутер.

    Использование:
        async def my_route(db: AsyncSession = Depends(get_db)): ...

    Сессия автоматически закрывается при выходе из блока async with,
    даже если роутер бросил исключение.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def check_db_connection() -> bool:
    """
    Проверяет доступность PostgreSQL.
    Используется health-endpoint'ом (/health).
    """
    try:
        from sqlalchemy import text
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
