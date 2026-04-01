"""
Test configuration for Workflow Service.

JWT isolation:
  - Generates an RSA key pair at test session start.
  - Writes public key to tests/fixtures/jwt_public.pem.
  - Sets JWT_PUBLIC_KEY_PATH so the service verifies tokens locally.

DB isolation:
  - Uses aiosqlite in-memory SQLite (no PostgreSQL needed).
  - SQLAlchemy creates all tables from metadata before tests.
  - lock_manager.notify_catalog_lock is patched to a no-op.
"""
from __future__ import annotations
import os
import time
from pathlib import Path
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ── Fixtures directory ─────────────────────────────────────────────────────────
FIXTURES_DIR = Path(__file__).parent / "fixtures"
PRIVATE_KEY_PATH = FIXTURES_DIR / "jwt_private.pem"
PUBLIC_KEY_PATH = FIXTURES_DIR / "jwt_public.pem"


def _ensure_test_keys():
    FIXTURES_DIR.mkdir(exist_ok=True)
    if not PRIVATE_KEY_PATH.exists() or not PUBLIC_KEY_PATH.exists():
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, PublicFormat, NoEncryption,
        )
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        PRIVATE_KEY_PATH.write_bytes(
            key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())
        )
        PUBLIC_KEY_PATH.write_bytes(
            key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        )


_ensure_test_keys()

# ── Set env vars before importing app ─────────────────────────────────────────
os.environ["JWT_PUBLIC_KEY_PATH"] = str(PUBLIC_KEY_PATH)
os.environ["INTERNAL_API_SECRET"] = "test_secret"
os.environ["CATALOG_INTERNAL_URL"] = "http://catalog-mock:8002"

# ── Token helper ───────────────────────────────────────────────────────────────
PROJECT = "aaaaaaaa-0000-0000-0000-000000000001"
CUSTOMER_PM_ID = str(uuid4())
CONTRACTOR_PM_ID = str(uuid4())
ANALYST_ID = str(uuid4())
ORG_ID = str(uuid4())


def make_token(
    user_id: str | None = None,
    org_id: str | None = None,
    roles: list[dict] | None = None,
    is_superadmin: bool = False,
    exp_offset: int = 3600,
) -> str:
    import jwt

    if user_id is None:
        user_id = str(uuid4())
    if org_id is None:
        org_id = ORG_ID

    now = int(time.time())
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "roles": roles or [],
        "is_superadmin": is_superadmin,
        "iat": now,
        "exp": now + exp_offset,
        "jti": str(uuid4()),
    }
    private_key = PRIVATE_KEY_PATH.read_text()
    return jwt.encode(payload, private_key, algorithm="RS256")


def pm_customer_token() -> str:
    return make_token(
        user_id=CUSTOMER_PM_ID,
        roles=[{"project_id": PROJECT, "role": "pm", "side": "customer"}],
    )


def pm_contractor_token() -> str:
    return make_token(
        user_id=CONTRACTOR_PM_ID,
        roles=[{"project_id": PROJECT, "role": "pm", "side": "contractor"}],
    )


def analyst_customer_token() -> str:
    return make_token(
        user_id=ANALYST_ID,
        roles=[{"project_id": PROJECT, "role": "analyst", "side": "customer"}],
    )


def pm_customer_headers() -> dict:
    return {"Authorization": f"Bearer {pm_customer_token()}"}


def pm_contractor_headers() -> dict:
    return {"Authorization": f"Bearer {pm_contractor_token()}"}


def analyst_headers() -> dict:
    return {"Authorization": f"Bearer {analyst_customer_token()}"}


def internal_headers() -> dict:
    return {"X-Internal-Secret": "test_secret"}


# ── Database fixture ───────────────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    from app.database import Base
    from app.models import approval, audit  # noqa: F401 — register models

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


# ── App fixture ────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def test_app(test_session_factory):
    """FastAPI app with test DB and mocked lock_manager."""
    from app.main import app
    from app.database import get_db

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.main.init_db", new_callable=AsyncMock),
        patch("app.main.check_db_connection", return_value=True),
        patch("app.services.approval_service.lock_manager.notify_catalog_lock", new_callable=AsyncMock),
    ):
        yield app

    app.dependency_overrides.clear()
