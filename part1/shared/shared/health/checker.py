from __future__ import annotations
from typing import Callable, Awaitable
from fastapi import APIRouter

health_router = APIRouter()

_db_checker: Callable[[], Awaitable[bool]] | None = None


def set_db_checker(checker: Callable[[], Awaitable[bool]]) -> None:
    global _db_checker
    _db_checker = checker


@health_router.get("/health")
async def health() -> dict:
    db_status = "connected"
    if _db_checker is not None:
        try:
            ok = await _db_checker()
            db_status = "connected" if ok else "disconnected"
        except Exception:
            db_status = "disconnected"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "version": "1.0.0",
    }
