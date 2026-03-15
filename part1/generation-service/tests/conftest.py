"""
Общие фикстуры для тестов Generation Service.

JWT-проверка — тестовыми RSA-ключами (аналогично Catalog Service).
Вызов к Catalog /internal/render-bundle — мокается фикстурой из
docs/render-bundle-example.json.
"""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, NoEncryption, PublicFormat,
)
from httpx import AsyncClient, ASGITransport

# ── Путь к фикстурам ──────────────────────────────────────────────────────────
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
RENDER_BUNDLE_PATH = DOCS_DIR / "render-bundle-example.json"


@pytest.fixture(scope="session")
def render_bundle_fixture() -> dict:
    """Реальный render-bundle из docs/render-bundle-example.json."""
    with open(RENDER_BUNDLE_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── RSA-ключи для тестов ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def rsa_key_pair():
    """Генерирует тестовую пару RSA-ключей (сессионная — один раз на весь прогон)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()).decode()
    public_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    return {"private": private_pem, "public": public_pem, "key": key}


@pytest.fixture(scope="session")
def make_token(rsa_key_pair):
    """Фабрика JWT-токенов, подписанных тестовым приватным ключом."""
    def _make(user_id: str | None = None, org_id: str | None = None, roles: list | None = None) -> str:
        import time
        payload = {
            "sub": user_id or str(uuid.uuid4()),
            "org_id": org_id or str(uuid.uuid4()),
            "roles": roles or [],
            "is_superadmin": False,
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
        }
        return pyjwt.encode(payload, rsa_key_pair["private"], algorithm="RS256")
    return _make


# ── Тестовое FastAPI-приложение ────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_app(rsa_key_pair, render_bundle_fixture):
    """
    Поднимает app с:
    - Mocked MinIO (put_object, presigned_get_url, get_object_bytes, stat_object)
    - Mocked JWT (JWKS возвращает тестовый публичный ключ без HTTP-запроса)
    - Mocked Catalog /internal/render-bundle (возвращает фикстуру)
    """
    os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")

    from app.main import app
    from app.services.job_manager import get_job_manager, _manager
    import app.services.job_manager as jm_module

    # Сбрасываем синглтон менеджера перед каждым тестом
    jm_module._manager = None

    # Мок MinIO
    mock_minio = AsyncMock()
    mock_minio.bucket = "documents"
    mock_minio.templates_bucket = "templates"
    mock_minio.put_object = AsyncMock(return_value="abc123checksum")
    mock_minio.presigned_get_url = AsyncMock(return_value="http://minio/presigned/file.docx")
    mock_minio.get_object_bytes = AsyncMock(return_value=b"fake-file-content")
    mock_minio.stat_object = AsyncMock(return_value={"size": 1024, "etag": "abc"})

    # JWT verification mock: возвращает TokenPayload без HTTP к Auth
    async def mock_jwt_auth(request):
        from shared.schemas.user import TokenPayload
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Missing token"})
        token = auth_header.split(" ", 1)[1]
        payload = pyjwt.decode(
            token,
            rsa_key_pair["public"],
            algorithms=["RS256"],
        )
        return TokenPayload(
            sub=uuid.UUID(payload["sub"]),
            org_id=uuid.UUID(payload["org_id"]),
            roles=[],
            exp=payload["exp"],
            iat=payload["iat"],
        )

    # Мок Catalog render-bundle endpoint
    async def mock_fetch_bundle(document_id: str) -> dict:
        return render_bundle_fixture

    with (
        patch("app.storage.minio_client._minio", mock_minio),
        patch("app.storage.minio_client.get_minio_client", return_value=mock_minio),
        patch("app.api.deps._jwt_auth", side_effect=mock_jwt_auth),
        patch("app.services.generation_service._fetch_render_bundle", side_effect=mock_fetch_bundle),
    ):
        yield app


@pytest_asyncio.fixture
async def client(test_app, make_token):
    """HTTP-клиент с Bearer-токеном."""
    token = make_token()
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c
