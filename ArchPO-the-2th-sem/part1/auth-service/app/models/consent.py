from __future__ import annotations
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    purpose = Column(String(100), nullable=False)
    granted_at = Column(DateTime, server_default=func.now())
    revoked_at = Column(DateTime)
    ip_address = Column(String(45))

    user = relationship("User", back_populates="consent_records")
