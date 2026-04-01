from __future__ import annotations
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

class Base(DeclarativeBase):
    pass

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


async def init_db(url: str | None = None) -> None:
    global _engine, _session_factory
    if url is None:
        url = get_settings().DATABASE_URL
    _engine = create_async_engine(url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    assert _session_factory is not None, "DB not initialized"
    async with _session_factory() as session:
        yield session


async def check_db_connection() -> bool:
    if _engine is None:
        return False
    try:
        from sqlalchemy import text
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_engine() -> AsyncEngine | None:
    return _engine
