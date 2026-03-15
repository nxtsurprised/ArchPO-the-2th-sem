"""Интеграционные тесты API Generation Service."""
from __future__ import annotations
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


# ── /health ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── POST /api/generation/jobs ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_job_returns_202(client):
    resp = await client.post("/api/generation/jobs", json={
        "document_id": "doc-001",
        "format": "docx",
    })
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] in ("pending", "processing", "completed")


@pytest.mark.asyncio
async def test_create_job_idempotency(client):
    """Повторный запрос для того же document_id+format → тот же job_id."""
    payload = {"document_id": "doc-idempotent", "format": "xlsx"}
    resp1 = await client.post("/api/generation/jobs", json=payload)
    resp2 = await client.post("/api/generation/jobs", json=payload)
    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert resp1.json()["job_id"] == resp2.json()["job_id"]


@pytest.mark.asyncio
async def test_create_job_no_auth(test_app):
    """Без токена → 401."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.post("/api/generation/jobs", json={"document_id": "x", "format": "docx"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_job_invalid_format(client):
    """Неверный format → 422."""
    resp = await client.post("/api/generation/jobs", json={
        "document_id": "doc-001",
        "format": "pdf",  # не поддерживается
    })
    assert resp.status_code == 422


# ── GET /api/generation/jobs/:job_id ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_status(client):
    create_resp = await client.post("/api/generation/jobs", json={
        "document_id": "doc-status-test",
        "format": "docx",
    })
    job_id = create_resp.json()["job_id"]

    resp = await client.get(f"/api/generation/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert "status" in data
    assert "progress" in data


@pytest.mark.asyncio
async def test_get_job_not_found(client):
    resp = await client.get("/api/generation/jobs/nonexistent-uuid")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"


# ── GET /api/generation/jobs/:job_id/download ─────────────────────────────────

@pytest.mark.asyncio
async def test_download_not_completed_job(client):
    """Скачивание job-а в статусе pending → 409."""
    create_resp = await client.post("/api/generation/jobs", json={
        "document_id": "doc-download-pending",
        "format": "docx",
    })
    job_id = create_resp.json()["job_id"]

    # Сразу пытаемся скачать — job ещё не completed (пайплайн async)
    # Может быть pending или completed (в тесте пайплайн может завершиться)
    resp = await client.get(f"/api/generation/jobs/{job_id}/download", follow_redirects=False)
    assert resp.status_code in (302, 409)  # 302 если успел, 409 если ещё pending


@pytest.mark.asyncio
async def test_download_nonexistent_job(client):
    resp = await client.get("/api/generation/jobs/fake-job-id/download", follow_redirects=False)
    assert resp.status_code == 404


# ── GET /api/generation/documents/:document_id/files ─────────────────────────

@pytest.mark.asyncio
async def test_list_document_files_empty(client):
    resp = await client.get("/api/generation/documents/no-such-doc/files")
    assert resp.status_code == 200
    assert resp.json() == []


# ── /internal/audit ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_internal_audit_no_secret(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/internal/audit")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_internal_audit_with_secret(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/internal/audit", headers={"X-Internal-Secret": "internal_secret"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
