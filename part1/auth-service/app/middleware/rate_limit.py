from __future__ import annotations
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI


def _make_limiter() -> Limiter:
    """
    Создаёт Limiter с Redis-бекендом если REDIS_URL задан,
    иначе использует in-memory хранилище (подходит для одного инстанса).
    Redis гарантирует корректную работу при нескольких репликах сервиса.
    """
    redis_url = os.getenv("REDIS_URL")
    storage_uri = redis_url if redis_url else "memory://"
    return Limiter(key_func=get_remote_address, storage_uri=storage_uri)


limiter = _make_limiter()


def setup_rate_limiter(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
