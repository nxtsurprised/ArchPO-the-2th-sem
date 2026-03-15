from __future__ import annotations
import asyncio
import time
from typing import Any


class CacheService:
    """
    Простой in-memory кеш с поддержкой TTL.

    MVP-реализация: обычный dict, защищённый asyncio.Lock.
    В v2 предполагается замена на Redis/Valkey без изменения интерфейса.

    Хранилище: { key -> (value, expires_at) }
    expires_at – абсолютное время по time.monotonic() (не подвержено NTP-прыжкам).
    """

    def __init__(self):
        # Словарь: ключ -> (значение, время истечения в монотонных секундах)
        self._store: dict[str, tuple[Any, float]] = {}
        # Мьютекс нужен, так как несколько корутин могут обращаться к кешу одновременно
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Возвращает значение или None, если ключ отсутствует или просрочен."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            # Ленивое удаление – удаляем просроченную запись только при обращении
            if expires_at and time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Сохраняет значение с указанным временем жизни в секундах."""
        async with self._lock:
            # expires_at = 0.0 означает "без срока" (используется редко)
            expires_at = time.monotonic() + ttl_seconds if ttl_seconds else 0.0
            self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        """Удаляет ключ. Не бросает исключение, если ключа нет."""
        async with self._lock:
            self._store.pop(key, None)
