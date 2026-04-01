"""create approval tables

Revision ID: 001
Revises:
Create Date: 2026-03-01 00:00:00.000000

"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(100), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("initiated_by", sa.String(36), nullable=False),
        sa.Column("initiated_by_side", sa.String(20), nullable=False),
        sa.Column("current_round", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_locked", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_approval_requests_document_id", "approval_requests", ["document_id"])
    op.create_index("ix_approval_requests_project_id", "approval_requests", ["project_id"])

    # Partial unique index: only one active non-review pending approval per document
    op.execute(
        "CREATE UNIQUE INDEX uq_approval_pending_non_review "
        "ON approval_requests (document_id) "
        "WHERE status = 'pending' AND type != 'review'"
    )

    op.create_table(
        "approval_rounds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("final_decision", sa.String(20), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("round_id", sa.String(36), sa.ForeignKey("approval_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("user_role", sa.String(20), nullable=False),
        sa.Column("user_side", sa.String(20), nullable=False),
        sa.Column("decision_type", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # Uniqueness per (round_id, user_id, decision_type) enforced at application level.
    # A user may submit one "review" AND one binding decision in the same round.

    op.create_table(
        "approval_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("target_section", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("result", sa.String(20), nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("service", sa.String(20), nullable=True, server_default="workflow"),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_project_id", "audit_log", ["project_id"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("approval_comments")
    op.drop_table("approval_decisions")
    op.drop_table("approval_rounds")
    op.drop_table("approval_requests")
