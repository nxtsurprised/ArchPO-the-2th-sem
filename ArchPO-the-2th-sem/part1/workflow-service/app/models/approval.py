"""
ORM-модели процесса согласования.

Иерархия объектов:
  ApprovalRequest          — один запрос на согласование (1 на документ в момент времени)
    └─ ApprovalRound[]     — раунды (1..*), создаётся новый при каждом "revision"
         └─ ApprovalDecision[] — решения участников в данном раунде
  ApprovalComment[]        — комментарии к запросу (не влияют на исход, только для общения)

Стратегия загрузки `lazy="selectin"` (не "lazy"):
  При чтении ApprovalRequest SQLAlchemy автоматически делает отдельный SELECT IN для
  rounds/comments — это безопаснее чем joinedload (нет дублирования строк при нескольких
  отношениях) и не требует явного selectinload() при каждом запросе.
  Но после flush() новых дочерних объектов коллекция в памяти может устареть —
  в таких случаях нужен явный db.refresh(obj, attribute_names=[...]).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(100), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)
    type = Column(String(20), nullable=False)               # tz_final | nmck_final | review
    status = Column(String(20), default="pending", nullable=False)  # pending | approved | rejected | revision | cancelled
    initiated_by = Column(String(36), nullable=False)
    initiated_by_side = Column(String(20), nullable=False)  # customer | contractor
    current_round = Column(Integer, default=1, nullable=False)
    # is_locked отражает должен ли документ в Catalog быть заблокирован для редактирования.
    # True при pending/approved, False при rejected/revision/cancelled.
    is_locked = Column(Boolean, default=True, nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    # order_by гарантирует что rounds[0] — первый раунд, rounds[-1] — текущий
    rounds = relationship("ApprovalRound", back_populates="request", lazy="selectin", order_by="ApprovalRound.round_number")
    comments = relationship("ApprovalComment", back_populates="request", lazy="selectin", order_by="ApprovalComment.created_at")


class ApprovalRound(Base):
    __tablename__ = "approval_rounds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(36), ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False)
    round_number = Column(Integer, nullable=False)
    status = Column(String(20), default="active", nullable=False)  # active | completed | cancelled
    # final_decision заполняется только когда раунд завершается (status → completed)
    final_decision = Column(String(20), nullable=True)             # approved | rejected | revision
    started_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    request = relationship("ApprovalRequest", back_populates="rounds")
    decisions = relationship("ApprovalDecision", back_populates="round", lazy="selectin", order_by="ApprovalDecision.decided_at")


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    round_id = Column(String(36), ForeignKey("approval_rounds.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), nullable=False)
    user_role = Column(String(20), nullable=False)   # pm | analyst
    user_side = Column(String(20), nullable=False)   # customer | contractor
    # decision_type: "review" — информационное (не влияет на исход раунда)
    #                "approve" | "reject" | "revision" — финальное (учитывается в evaluate_round)
    decision_type = Column(String(20), nullable=False)
    comment = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    round = relationship("ApprovalRound", back_populates="decisions")


class ApprovalComment(Base):
    """Произвольный комментарий к запросу на согласование.

    Не влияет на статус/исход согласования — только для общения участников.
    target_section позволяет привязать комментарий к конкретному разделу документа.
    """
    __tablename__ = "approval_comments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(36), ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), nullable=False)
    text = Column(Text, nullable=False)
    target_section = Column(String(20), nullable=True)  # например "4.2", "7" — раздел документа
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    request = relationship("ApprovalRequest", back_populates="comments")
