"""
Integration tests for the full approval workflow.

Uses in-memory SQLite + mocked lock_manager.
Full flow: submit → review (analyst) → revision (both PMs) → new round → approve (both PMs) → approved.
"""
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport

from tests.conftest import (
    PROJECT,
    CUSTOMER_PM_ID,
    CONTRACTOR_PM_ID,
    ANALYST_ID,
    pm_customer_headers,
    pm_contractor_headers,
    analyst_headers,
    internal_headers,
    make_token,
)

DOCUMENT_ID = "doc-test-001"


# ── Auth guard ─────────────────────────────────────────────────────────────────

async def test_list_approvals_requires_auth(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/api/workflow/approvals")
    assert resp.status_code == 401


async def test_health(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ── Internal secret guard ──────────────────────────────────────────────────────

async def test_internal_status_requires_secret(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get(f"/internal/documents/{DOCUMENT_ID}/status")
    assert resp.status_code == 403


async def test_internal_status_with_secret_no_approval(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get(
            "/internal/documents/no-such-doc/status",
            headers=internal_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    assert data["locked"] is False


# ── round_evaluator unit ───────────────────────────────────────────────────────

def test_evaluate_round_both_approve():
    from app.services.round_evaluator import evaluate_round
    from dataclasses import dataclass

    @dataclass
    class D:
        decision_type: str
        user_side: str

    result = evaluate_round(
        [D("approve", "customer"), D("approve", "contractor")],
        "tz_final",
    )
    assert result == "approved"


# ── Full integration flow ──────────────────────────────────────────────────────

async def test_full_approval_flow(test_app):
    """
    Full flow:
    1. PM customer submits tz_final approval
    2. Analyst customer submits a review (informational)
    3. PM customer decides "revision"
    4. PM contractor decides "revision" → round 1 closes as "revision"
    5. PM customer decides "approve" → triggers new round (round 2)
    6. PM contractor decides "approve" → round 2 closes as "approved"
    """
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:

        # Step 1: Submit approval
        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": DOCUMENT_ID, "project_id": PROJECT, "type": "tz_final"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 201, resp.text
        approval_id = resp.json()["id"]
        assert resp.json()["status"] == "pending"
        assert resp.json()["is_locked"] is True
        assert resp.json()["current_round"] == 1

        # Step 2: Analyst reviews (informational, does not close round)
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "review", "comment": "Looks mostly fine, minor suggestions"},
            headers=analyst_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "pending"   # still open
        assert data["current_round"] == 1

        # Step 3: PM customer decides "revision"
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "revision", "comment": "Section 4.2 needs rework"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "pending"  # waiting for contractor

        # Step 4: PM contractor decides "revision" → round 1 closes
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "revision", "comment": "Agreed, needs update"},
            headers=pm_contractor_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "revision"
        assert data["is_locked"] is False
        assert data["current_round"] == 1

        # Step 5: PM customer decides "approve" → triggers round 2
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "approve", "comment": "Updated, looks good now"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "pending"   # new round opened
        assert data["current_round"] == 2

        # Step 6: PM contractor approves → round 2 closes as approved
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "approve"},
            headers=pm_contractor_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "approved"
        assert data["current_round"] == 2
        assert data["is_locked"] is True

        # Verify history has 2 rounds
        resp = await c.get(
            f"/api/workflow/approvals/{approval_id}/history",
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 200
        rounds = resp.json()["rounds"]
        assert len(rounds) == 2
        assert rounds[0]["final_decision"] == "revision"
        assert rounds[1]["final_decision"] == "approved"


async def test_duplicate_submission_raises_409(test_app):
    """Cannot submit a second tz_final while one is already pending."""
    doc_id = "doc-dup-test-001"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": doc_id, "project_id": PROJECT, "type": "tz_final"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 201

        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": doc_id, "project_id": PROJECT, "type": "tz_final"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "APPROVAL_EXISTS"


async def test_analyst_cannot_make_binding_decision(test_app):
    """Analyst can only submit 'review', not 'approve'/'reject'/'revision' for tz_final."""
    doc_id = "doc-analyst-test-001"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": doc_id, "project_id": PROJECT, "type": "tz_final"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 201
        approval_id = resp.json()["id"]

        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "approve"},
            headers=analyst_headers(),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_cannot_decide_twice(test_app):
    """User cannot submit two non-review decisions in the same round."""
    doc_id = "doc-twice-test-001"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": doc_id, "project_id": PROJECT, "type": "tz_final"},
            headers=pm_customer_headers(),
        )
        approval_id = resp.json()["id"]

        # First decision
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "approve"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 200

        # Second decision
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "revision"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "ALREADY_DECIDED"


async def test_revoke_decision(test_app):
    """PM can revoke their decision while round is still active."""
    doc_id = "doc-revoke-test-001"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": doc_id, "project_id": PROJECT, "type": "tz_final"},
            headers=pm_customer_headers(),
        )
        approval_id = resp.json()["id"]

        # Submit decision
        await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "approve"},
            headers=pm_customer_headers(),
        )

        # Revoke
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/revoke",
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 200

        # Can decide again after revoke
        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "revision"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 200


async def test_cancel_approval(test_app):
    """PM can cancel a pending approval."""
    doc_id = "doc-cancel-test-001"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": doc_id, "project_id": PROJECT, "type": "tz_final"},
            headers=pm_customer_headers(),
        )
        approval_id = resp.json()["id"]

        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/cancel",
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["is_locked"] is False


async def test_dashboard(test_app):
    """Dashboard returns counts per status."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get(
            f"/api/workflow/dashboard?project_id={PROJECT}",
            headers=pm_customer_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "pending" in data
    assert "approved" in data
    assert "total" in data


async def test_internal_audit_with_secret(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.get(
            f"/internal/audit?project_id={PROJECT}",
            headers=internal_headers(),
        )
    assert resp.status_code == 200
    assert "items" in resp.json()


async def test_review_type_does_not_lock(test_app):
    """review-type approval does not lock the document."""
    doc_id = "doc-review-type-001"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": doc_id, "project_id": PROJECT, "type": "review"},
            headers=pm_customer_headers(),
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_locked"] is False


async def test_nmck_final_approved(test_app):
    """nmck_final approval flow: both PMs approve in one round."""
    doc_id = "doc-nmck-test-001"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        resp = await c.post(
            "/api/workflow/approvals",
            json={"document_id": doc_id, "project_id": PROJECT, "type": "nmck_final"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 201
        approval_id = resp.json()["id"]

        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "approve"},
            headers=pm_customer_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"  # waiting for contractor

        resp = await c.post(
            f"/api/workflow/approvals/{approval_id}/decide",
            json={"decision": "approve"},
            headers=pm_contractor_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
