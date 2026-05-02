"""
Test configuration for Catalog Service.

JWT isolation:
  - Generates an RSA key pair at test session start.
  - Writes public key to tests/fixtures/jwt_public.pem.
  - Sets JWT_PUBLIC_KEY_PATH so the service verifies tokens locally —
    no real Auth Service is needed.

DB isolation:
  - Uses mongomock-motor (in-memory MongoDB compatible with Motor/Beanie).
  - Beanie is re-initialised for every test session.
"""
from __future__ import annotations
import os
from pathlib import Path
from uuid import uuid4

import beanie
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient

# ── Fixtures directory ─────────────────────────────────────────────────────────
FIXTURES_DIR = Path(__file__).parent / "fixtures"
PRIVATE_KEY_PATH = FIXTURES_DIR / "jwt_private.pem"
PUBLIC_KEY_PATH = FIXTURES_DIR / "jwt_public.pem"


def _ensure_test_keys():
    """Generate RSA key pair once per dev environment and persist to fixtures/."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    if not PRIVATE_KEY_PATH.exists() or not PUBLIC_KEY_PATH.exists():
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PrivateFormat,
            PublicFormat,
            NoEncryption,
        )

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        PRIVATE_KEY_PATH.write_bytes(
            key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())
        )
        PUBLIC_KEY_PATH.write_bytes(
            key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        )


_ensure_test_keys()


# ── Token helper ───────────────────────────────────────────────────────────────
def make_token(
    user_id: str | None = None,
    org_id: str | None = None,
    roles: list[dict] | None = None,
    is_superadmin: bool = False,
) -> str:
    """Sign a JWT with the test private key."""
    import time
    import jwt as pyjwt

    private_key = PRIVATE_KEY_PATH.read_text()
    payload = {
        "sub": user_id or str(uuid4()),
        "org_id": org_id or str(uuid4()),
        "roles": roles or [],
        "is_superadmin": is_superadmin,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, private_key, algorithm="RS256")


# ── App fixture ────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def test_app():
    """
    FastAPI app wired to:
      - in-memory MongoDB (mongomock-motor)
      - test JWT public key (no Auth Service calls)
    """
    # Point JWT verification at the test key file
    os.environ["JWT_PUBLIC_KEY_PATH"] = str(PUBLIC_KEY_PATH)
    os.environ["JWKS_URL"] = ""

    # Invalidate cached settings so env vars are picked up
    from app.config import get_settings
    get_settings.cache_clear()

    # Init Beanie with an in-memory client
    client = AsyncMongoMockClient()
    db = client["catalog_test"]

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

    # Patch database.init_db / check_db_connection so lifespan doesn't try real Mongo
    from unittest.mock import AsyncMock, patch
    from app.main import app
    import app.database as _db_module

    # Inject mock client so check_db_connection() doesn't see _motor_client=None
    _db_module._motor_client = client

    async def _noop_init(settings):
        pass  # Beanie already initialised above

    async def _mock_check_db():
        return True

    with (
        patch("app.main.init_db", new=_noop_init),
        patch("app.main.check_db_connection", new=_mock_check_db),
    ):
        yield app

    client.close()


@pytest.fixture
def auth_headers():
    """Bearer token for a pm user in a known project."""
    project_id = "aaaaaaaa-0000-0000-0000-000000000001"
    token = make_token(
        roles=[{"project_id": project_id, "role": "pm", "side": "customer"}]
    )
    return {"Authorization": f"Bearer {token}"}, project_id


@pytest.fixture
def analyst_headers():
    """Bearer token for an analyst user."""
    project_id = "aaaaaaaa-0000-0000-0000-000000000001"
    token = make_token(
        roles=[{"project_id": project_id, "role": "analyst", "side": "contractor"}]
    )
    return {"Authorization": f"Bearer {token}"}, project_id
