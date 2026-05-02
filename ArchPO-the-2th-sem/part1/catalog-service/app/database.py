"""
Инициализация подключения к MongoDB через Motor + Beanie.

Стек:
  Motor  — официальный async-драйвер MongoDB для Python (asyncio-совместимый).
  Beanie — ODM (Object-Document Mapper) поверх Motor: Pydantic-модели как документы,
           автоматические индексы, типизированные запросы.

Все модели должны быть переданы в beanie.init_beanie() при старте — это нужно для:
  1. Регистрации коллекций (имя берётся из Settings.name каждой модели).
  2. Создания объявленных индексов (если не существуют).
  3. Настройки валидации схемы документов.
"""
from __future__ import annotations
import beanie
from motor.motor_asyncio import AsyncIOMotorClient

_motor_client: AsyncIOMotorClient | None = None


async def init_db(settings) -> None:
    global _motor_client
    _motor_client = AsyncIOMotorClient(settings.MONGO_URL)
    db = _motor_client[settings.MONGO_DB]

    # Отложенные импорты — избегают циклических зависимостей при загрузке модуля
    from app.models.template import Template
    from app.models.function import Function
    from app.models.subsystem import Subsystem
    from app.models.rates import Rates
    from app.models.document import Document
    from app.models.audit import AuditLog

    await beanie.init_beanie(
        database=db,
        document_models=[Template, Function, Subsystem, Rates, Document, AuditLog],
    )


async def close_db() -> None:
    global _motor_client
    if _motor_client is not None:
        _motor_client.close()
        _motor_client = None


async def check_db_connection() -> bool:
    try:
        if _motor_client is None:
            return False
        await _motor_client.admin.command("ping")
        return True
    except Exception:
        return False
