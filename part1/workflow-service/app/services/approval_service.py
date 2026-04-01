from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.approval import ApprovalRequest, ApprovalRound, ApprovalDecision, ApprovalComment
from app.schemas.requests import ApprovalSubmit, DecisionCreate, CommentCreate
from app.api.deps import TokenPayload
from app.services.round_evaluator import evaluate_round
from app.services import audit_service
from app.services import lock_manager


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _load_full(db: AsyncSession, approval_id: str) -> ApprovalRequest | None:
    """Load ApprovalRequest with all nested relationships already in memory.

    Required before returning to FastAPI so Pydantic's synchronous model_validate
    doesn't trigger async lazy-loads (which raise MissingGreenlet errors).
    """
    result = await db.execute(
        select(ApprovalRequest)
        .options(
            selectinload(ApprovalRequest.rounds).selectinload(ApprovalRound.decisions)
        )
        .where(ApprovalRequest.id == approval_id)
    )
    return result.unique().scalars().first()


# ── Permission helpers ──────────────────────────────────────────────────────────

def _can_decide(
    approval_type: str,
    decision_type: str,
    role: str,
) -> bool:
    """Return True if role is allowed to submit this decision_type for this approval_type."""
    if approval_type == "review":
        # Only "review" decisions in a review request
        return decision_type == "review" and role in ("pm", "analyst", "superadmin")

    if decision_type == "review":
        # Informational review: pm and analyst allowed for tz_final; not for nmck_final
        if approval_type == "tz_final":
            return role in ("pm", "analyst", "superadmin")
        return False  # nmck_final has no reviews

    # Binding decisions (approve | reject | revision): only pm
    if decision_type in ("approve", "reject", "revision"):
        if approval_type == "tz_final":
            return role in ("pm", "superadmin")
        if approval_type == "nmck_final":
            return role in ("pm", "superadmin")
    return False


# ── Submit ──────────────────────────────────────────────────────────────────────

async def submit_approval(
    db: AsyncSession,
    data: ApprovalSubmit,
    user: TokenPayload,
    user_role: str,
    user_side: str,
) -> ApprovalRequest:
    # Check for existing active (non-review) pending approval on this document
    if data.type != "review":
        result = await db.execute(
            select(ApprovalRequest).where(
                and_(
                    ApprovalRequest.document_id == data.document_id,
                    ApprovalRequest.status == "pending",
                    ApprovalRequest.type != "review",
                )
            )
        )
        existing = result.scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "APPROVAL_EXISTS",
                    "message": "An active non-review approval already exists for this document",
                },
            )

    is_locked = data.type != "review"

    approval = ApprovalRequest(
        document_id=data.document_id,
        project_id=data.project_id,
        type=data.type,
        status="pending",
        initiated_by=str(user.sub),
        initiated_by_side=user_side,
        current_round=1,
        is_locked=is_locked,
    )
    db.add(approval)
    await db.flush()  # get approval.id

    first_round = ApprovalRound(
        request_id=approval.id,
        round_number=1,
        status="active",
    )
    db.add(first_round)

    if is_locked:
        await lock_manager.notify_catalog_lock(data.document_id, locked=True, status="pending")

    await audit_service.write_audit(
        db,
        action="approval.submit",
        user_id=str(user.sub),
        resource_type="approval",
        resource_id=approval.id,
        project_id=data.project_id,
        details={"document_id": data.document_id, "type": data.type},
    )

    await db.commit()
    return await _load_full(db, approval.id)


# ── Get ─────────────────────────────────────────────────────────────────────────

async def get_approval(db: AsyncSession, approval_id: str) -> ApprovalRequest | None:
    return await _load_full(db, approval_id)


async def list_approvals(
    db: AsyncSession,
    project_id: str | None = None,
    approval_status: str | None = None,
    user_id: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[ApprovalRequest], int]:
    q = select(ApprovalRequest)
    filters = []
    if project_id:
        filters.append(ApprovalRequest.project_id == project_id)
    if approval_status:
        filters.append(ApprovalRequest.status == approval_status)
    if user_id:
        filters.append(ApprovalRequest.initiated_by == user_id)
    if filters:
        q = q.where(and_(*filters))

    count_result = await db.execute(q)
    total = len(count_result.scalars().all())

    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    items = result.scalars().all()
    return list(items), total


# ── Decide ──────────────────────────────────────────────────────────────────────

async def decide(
    db: AsyncSession,
    approval_id: str,
    data: DecisionCreate,
    user: TokenPayload,
    user_role: str,
    user_side: str,
) -> ApprovalRequest:
    approval = await get_approval(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})

    # If request is in revision state, auto-create a new round
    if approval.status == "revision":
        approval.status = "pending"
        approval.current_round += 1
        approval.updated_at = _now()

        new_round = ApprovalRound(
            request_id=approval.id,
            round_number=approval.current_round,
            status="active",
        )
        db.add(new_round)
        await db.flush()

        if approval.type != "review":
            await lock_manager.notify_catalog_lock(
                approval.document_id, locked=True, status="pending"
            )

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "APPROVAL_NOT_PENDING", "message": f"Approval is {approval.status}"},
        )

    # Validate permission
    if not _can_decide(approval.type, data.decision, user_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": f"Role '{user_role}' cannot submit '{data.decision}' for type '{approval.type}'",
            },
        )

    # Find the current active round (query directly to avoid stale cache)
    round_result = await db.execute(
        select(ApprovalRound)
        .options(selectinload(ApprovalRound.decisions))
        .where(
            and_(
                ApprovalRound.request_id == approval.id,
                ApprovalRound.status == "active",
                ApprovalRound.round_number == approval.current_round,
            )
        )
    )
    active_round = round_result.scalars().first()

    if active_round is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NO_ACTIVE_ROUND", "message": "No active round found"},
        )

    # One non-review decision per user per round (review can be submitted regardless)
    if data.decision != "review":
        existing = next(
            (
                d
                for d in active_round.decisions
                if d.user_id == str(user.sub) and d.decision_type != "review"
            ),
            None,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ALREADY_DECIDED", "message": "You have already submitted a decision for this round"},
            )
    else:
        existing_review = next(
            (d for d in active_round.decisions if d.user_id == str(user.sub) and d.decision_type == "review"),
            None,
        )
        if existing_review:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ALREADY_REVIEWED", "message": "You have already submitted a review for this round"},
            )

    decision_obj = ApprovalDecision(
        round_id=active_round.id,
        user_id=str(user.sub),
        user_role=user_role,
        user_side=user_side,
        decision_type=data.decision,
        comment=data.comment,
    )
    db.add(decision_obj)
    await db.flush()

    # Reload round decisions including the new one (explicit selectinload to avoid lazy-load in sync context)
    round_reload = await db.execute(
        select(ApprovalRound)
        .options(selectinload(ApprovalRound.decisions))
        .where(ApprovalRound.id == active_round.id)
    )
    active_round = round_reload.scalars().first()

    # Evaluate round outcome
    outcome = evaluate_round(active_round.decisions, approval.type)

    if outcome is not None:
        active_round.status = "completed"
        active_round.final_decision = outcome
        active_round.completed_at = _now()

        approval.status = outcome
        approval.updated_at = _now()

        # Lock/unlock catalog document based on outcome
        if approval.type != "review":
            if outcome == "approved":
                approval.is_locked = True
                await lock_manager.notify_catalog_lock(
                    approval.document_id, locked=True, status="approved"
                )
            elif outcome in ("rejected", "revision"):
                approval.is_locked = False
                catalog_status = "rejected" if outcome == "rejected" else "draft"
                await lock_manager.notify_catalog_lock(
                    approval.document_id, locked=False, status=catalog_status
                )

        await audit_service.write_audit(
            db,
            action="approval.round_closed",
            user_id=str(user.sub),
            resource_type="approval",
            resource_id=approval.id,
            project_id=approval.project_id,
            details={"round_number": active_round.round_number, "final_decision": outcome},
        )

    await audit_service.write_audit(
        db,
        action="approval.decide",
        user_id=str(user.sub),
        resource_type="approval",
        resource_id=approval.id,
        project_id=approval.project_id,
        details={"decision_type": data.decision, "comment": data.comment},
    )

    await db.commit()
    return await _load_full(db, approval.id)


# ── Revoke ──────────────────────────────────────────────────────────────────────

async def revoke_decision(
    db: AsyncSession,
    approval_id: str,
    user: TokenPayload,
    user_role: str,
) -> ApprovalRequest:
    approval = await get_approval(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})

    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ROUND_COMPLETED", "message": "Cannot revoke: round already completed"},
        )

    if user_role not in ("pm", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Only PM can revoke decisions"},
        )

    # Find the active round (direct query)
    round_result = await db.execute(
        select(ApprovalRound).where(
            and_(
                ApprovalRound.request_id == approval.id,
                ApprovalRound.status == "active",
                ApprovalRound.round_number == approval.current_round,
            )
        )
    )
    active_round = round_result.scalars().first()
    if active_round is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NO_ACTIVE_ROUND", "message": "No active round found"},
        )

    # Find user's non-review decision
    dec_result = await db.execute(
        select(ApprovalDecision).where(
            and_(
                ApprovalDecision.round_id == active_round.id,
                ApprovalDecision.user_id == str(user.sub),
                ApprovalDecision.decision_type != "review",
            )
        )
    )
    user_decision = dec_result.scalars().first()
    if user_decision is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "No decision found to revoke"},
        )

    revoked_type = user_decision.decision_type
    await db.delete(user_decision)

    await audit_service.write_audit(
        db,
        action="approval.revoke",
        user_id=str(user.sub),
        resource_type="approval",
        resource_id=approval.id,
        project_id=approval.project_id,
        details={"revoked_decision_type": revoked_type},
    )

    await db.commit()
    return await _load_full(db, approval.id)


# ── Cancel ──────────────────────────────────────────────────────────────────────

async def cancel_approval(
    db: AsyncSession,
    approval_id: str,
    user: TokenPayload,
    user_role: str,
) -> ApprovalRequest:
    approval = await get_approval(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})

    if user_role not in ("pm", "admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Only PM or admin can cancel approvals"},
        )

    if approval.status not in ("pending", "revision"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CANNOT_CANCEL", "message": f"Cannot cancel approval in status '{approval.status}'"},
        )

    # Cancel all active rounds (direct query to avoid stale cache)
    active_rounds_result = await db.execute(
        select(ApprovalRound).where(
            and_(ApprovalRound.request_id == approval.id, ApprovalRound.status == "active")
        )
    )
    for r in active_rounds_result.scalars().all():
        r.status = "cancelled"
        r.completed_at = _now()

    approval.status = "cancelled"
    approval.is_locked = False
    approval.updated_at = _now()

    await lock_manager.notify_catalog_lock(approval.document_id, locked=False, status="draft")

    await audit_service.write_audit(
        db,
        action="approval.cancel",
        user_id=str(user.sub),
        resource_type="approval",
        resource_id=approval.id,
        project_id=approval.project_id,
        details={"cancelled_by_role": user_role},
    )

    await db.commit()
    return await _load_full(db, approval.id)


# ── Comments ────────────────────────────────────────────────────────────────────

async def add_comment(
    db: AsyncSession,
    approval_id: str,
    data: CommentCreate,
    user: TokenPayload,
) -> ApprovalComment:
    approval = await get_approval(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})

    comment = ApprovalComment(
        request_id=approval_id,
        user_id=str(user.sub),
        text=data.text,
        target_section=data.target_section,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


# ── Dashboard ───────────────────────────────────────────────────────────────────

async def get_dashboard(
    db: AsyncSession,
    project_id: str,
) -> dict[str, int]:
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.project_id == project_id)
    )
    approvals = result.scalars().all()

    counts: dict[str, int] = {"pending": 0, "approved": 0, "rejected": 0, "revision": 0}
    for a in approvals:
        if a.status in counts:
            counts[a.status] += 1

    return {**counts, "total": len(approvals)}


async def get_my_tasks(
    db: AsyncSession,
    user: TokenPayload,
    project_id: str,
    user_role: str,
    user_side: str,
) -> list[ApprovalRequest]:
    """Return pending approvals where user can still decide."""
    result = await db.execute(
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.rounds).selectinload(ApprovalRound.decisions))
        .where(
            and_(
                ApprovalRequest.project_id == project_id,
                ApprovalRequest.status == "pending",
            )
        )
    )
    approvals = result.unique().scalars().all()

    tasks = []
    for approval in approvals:
        active_round = next(
            (r for r in approval.rounds if r.status == "active" and r.round_number == approval.current_round),
            None,
        )
        if active_round is None:
            continue

        # Check if user already decided (non-review)
        already_decided = any(
            d.user_id == str(user.sub) and d.decision_type != "review"
            for d in active_round.decisions
        )
        if not already_decided and user_role in ("pm", "analyst", "superadmin"):
            tasks.append(approval)

    return tasks
