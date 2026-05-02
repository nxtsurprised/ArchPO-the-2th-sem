"""Auth service tests — unit + integration."""
from __future__ import annotations
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock


# ──────────────────────────── Unit tests ──────────────────────────────────────

def test_password_policy_too_short():
    from app.services.password import validate_password_policy
    errors = validate_password_policy("Short1!")
    assert any("символов" in e for e in errors)


def test_password_policy_not_enough_categories():
    from app.services.password import validate_password_policy
    errors = validate_password_policy("alllowercasepassword123")
    assert any("категори" in e for e in errors)


def test_password_policy_valid():
    from app.services.password import validate_password_policy
    assert validate_password_policy("SecurePass123!") == []


def test_password_hash_and_verify():
    from app.services.password import hash_password, verify_password
    hashed = hash_password("MyPass123!")
    assert verify_password("MyPass123!", hashed)
    assert not verify_password("WrongPass", hashed)


def test_mask_email():
    from app.api.admin import _mask_email
    assert _mask_email("ivanov@domain.ru") == "iva***@domain.ru"


def test_mask_name():
    from app.api.admin import _mask_name
    assert _mask_name("Иванов Иван Иванович") == "Иванов И.И."


def test_audit_diff_changes():
    from shared.services.audit_diff import compute_changes
    result = compute_changes({"a": 1, "b": 2}, {"a": 1, "b": 3})
    assert result == {"b": {"old": 2, "new": 3}}


def test_audit_diff_no_changes():
    from shared.services.audit_diff import compute_changes
    assert compute_changes({"a": 1}, {"a": 1}) is None


# ──────────────────────────── Integration test ────────────────────────────────

@pytest_asyncio.fixture
async def test_app():
    """App with SQLite in-memory DB for tests."""
    import os
    os.environ.setdefault("DB_HOST", "localhost")

    # Patch DB to use SQLite
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import StaticPool
    from app.database import Base, get_db

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Patch jwt key loading
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, NoEncryption, PublicFormat,
    )
    _key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _private_pem = _key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()).decode()
    _public_pem = _key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()

    async def override_get_db():
        async with factory() as session:
            yield session

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.services.jwt_service._load_private_key", return_value=_private_pem),
        patch("app.services.jwt_service._load_public_key", return_value=_public_pem),
        patch("app.database.check_db_connection", new_callable=AsyncMock, return_value=True),
    ):
        yield app

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_health(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_nonexistent_user(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"email": "no@example.com", "password": "pass"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_full_auth_flow(test_app):
    """Create user → login → get me → refresh → logout → refresh = 401."""
    from app.database import get_session_factory
    from app.models.user import Organization, User
    from app.services.password import hash_password
    from datetime import datetime, timezone, timedelta
    import uuid

    # Seed a user directly
    async with test_app.dependency_overrides[
        __import__("app.database", fromlist=["get_db"]).get_db
    ]().__aiter__().__anext__().__class__:
        pass  # just to verify override exists

    # Use the session override factory from fixture
    _get_db = test_app.dependency_overrides[
        __import__("app.database", fromlist=["get_db"]).get_db
    ]
    async for db in _get_db():
        org = Organization(id=uuid.uuid4(), name="TestOrg", inn="1234567890")
        db.add(org)
        await db.flush()
        user = User(
            organization_id=org.id,
            email="test@example.com",
            password_hash=hash_password("TestPass123!"),
            full_name="Тест Тестов",
            password_expires_at=(datetime.now(timezone.utc) + timedelta(days=90)).replace(tzinfo=None),
        )
        db.add(user)
        await db.commit()
        break

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Login
        resp = await client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        access_token = data["access_token"]
        refresh_cookie = resp.cookies.get("refresh_token")

        # GET /me
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

        # Refresh
        if refresh_cookie:
            client.cookies.set("refresh_token", refresh_cookie)
            resp = await client.post("/api/auth/refresh")
            assert resp.status_code == 200
            new_access = resp.json()["access_token"]
            new_refresh = resp.cookies.get("refresh_token")

            # Logout
            resp = await client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {new_access}"},
            )
            assert resp.status_code == 204

            # Old refresh should now be invalid
            if new_refresh:
                client.cookies.set("refresh_token", new_refresh)
                resp = await client.post("/api/auth/refresh")
                assert resp.status_code == 401


@pytest.mark.asyncio
async def test_five_failed_logins_locks_account(test_app):
    from app.database import get_session_factory
    from app.models.user import Organization, User
    from app.services.password import hash_password
    from datetime import datetime, timezone, timedelta
    import uuid

    _get_db = test_app.dependency_overrides[
        __import__("app.database", fromlist=["get_db"]).get_db
    ]
    async for db in _get_db():
        org = Organization(id=uuid.uuid4(), name="LockOrg", inn="9876543210")
        db.add(org)
        await db.flush()
        db.add(User(
            organization_id=org.id,
            email="lockme@example.com",
            password_hash=hash_password("CorrectPass123!"),
            full_name="Тест Блокировка",
            password_expires_at=(datetime.now(timezone.utc) + timedelta(days=90)).replace(tzinfo=None),
        ))
        await db.commit()
        break

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        for _ in range(5):
            resp = await client.post("/api/auth/login", json={
                "email": "lockme@example.com", "password": "WrongPass123!",
            })
            assert resp.status_code == 401

        resp = await client.post("/api/auth/login", json={
            "email": "lockme@example.com", "password": "CorrectPass123!",
        })
        assert resp.status_code == 423
