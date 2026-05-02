from __future__ import annotations
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Text, JSON

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    project_id = Column(String(36), nullable=True, index=True)
    result = Column(String(20), default="success")
    details = Column(JSON, nullable=True)
    service = Column(String(20), default="workflow")
