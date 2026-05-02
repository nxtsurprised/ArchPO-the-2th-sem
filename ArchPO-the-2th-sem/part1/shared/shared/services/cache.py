from __future__ import annotations
import asyncio
import time
from typing import Any
import structlog

logger = structlog.get_logger()


class CacheService:
    """
    Кеш с поддержкой TTL.

    Два режима работы:
    - Redis (рекомендуется для продакшена): передайте redis_url="redis://redis:6379/0"
    - In-memory fallback: если redis_url не задан или Redis недоступен.

    Интерфейс одинаков в обоих режимах — код сервисов не меняется.
    При недоступности Redis автоматически переключается на in-memory.
    """

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url
        self._redis: Any | None = None
        self._redis_failed = False            # флаг: Redis уже падал, не пробуем снова
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    # ──────────────────────────────────────────────────────────────────────
    # Redis connection
    # ──────────────────────────────────────────────────────────────────────

    async def _get_redis(self):
        """Возвращает Redis-клиент или None, если не настроен / недоступен."""
        if not self._redis_url or self._redis_failed:
            return None
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await client.ping()
            self._redis = client
            logger.info("redis_connected", url=self._redis_url)
            return self._redis
        except Exception as e:
            logger.warning("redis_unavailable_fallback_to_memory", error=str(e))
            self._redis_failed = True
            return None

    async def close(self) -> None:
        """Закрыть соединение с Redis при завершении работы приложения."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    # ──────────────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────────────

    async def get(self, key: str) -> Any | None:
        """Возвращает значение или None, если ключ отсутствует или просрочен."""
        import pickle
        r = await self._get_redis()
        if r is not None:
            try:
                raw = await r.get(key)
                if raw is None:
                    return None
                return pickle.loads(raw)
            except Exception as e:
                logger.warning("redis_get_error", key=key, error=str(e))
                # Не переходим на in-memory — просто промах кеша

        # In-memory fallback
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at and time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Сохраняет значение с указанным временем жизни в секундах."""
        import pickle
        r = await self._get_redis()
        if r is not None:
            try:
                raw = pickle.dumps(value)
                if ttl_seconds:
                    await r.setex(key, ttl_seconds, raw)
                else:
                    await r.set(key, raw)
                return
            except Exception as e:
                logger.warning("redis_set_error", key=key, error=str(e))

        # In-memory fallback
        async with self._lock:
            expires_at = time.monotonic() + ttl_seconds if ttl_seconds else 0.0
            self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        """Удаляет ключ. Не бросает исключение, если ключа нет."""
        r = await self._get_redis()
        if r is not None:
            try:
                await r.delete(key)
                return
            except Exception as e:
                logger.warning("redis_delete_error", key=key, error=str(e))

        async with self._lock:
            self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Проверяет наличие ключа (без чтения значения)."""
        r = await self._get_redis()
        if r is not None:
            try:
                return bool(await r.exists(key))
            except Exception as e:
                logger.warning("redis_exists_error", key=key, error=str(e))

        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            _, expires_at = entry
            if expires_at and time.monotonic() > expires_at:
                del self._store[key]
                return False
            return True
