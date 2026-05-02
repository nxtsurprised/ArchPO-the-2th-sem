from __future__ import annotations
import uuid
from sqlalchemy import Column, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_project_time", "project_id", "timestamp"),
        Index("idx_audit_user_time", "user_id", "timestamp"),
        Index("idx_audit_resource", "resource_id", "timestamp"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    user_side = Column(String(20))
    user_role = Column(String(20))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    service = Column(String(20), default="auth")
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=False)
    project_id = Column(UUID(as_uuid=True))
    correlation_id = Column(String(100))
    result = Column(String(20), default="success")
    changes = Column(JSONB)
    details = Column(JSONB)
