from __future__ import annotations
import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Session(Base):
    """
    Сессия пользователя, привязанная к refresh-токену.

    В БД хранится SHA-256 хеш refresh-токена, а не сам токен.
    Это означает, что утечка таблицы sessions не даёт злоумышленнику
    возможности использовать токены — оригинал получает только клиент
    в момент логина.

    Ротация токенов: при refresh старая сессия (is_revoked=True) заменяется
    новой. Если один и тот же токен используется дважды — первое использование
    уже revoked — сигнал компрометации.

    ip_address может содержать IPv4 (до 15 символов) или IPv6 (до 45 символов).
    """
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    refresh_token_hash = Column(String(255), nullable=False)  # sha256(raw_token)
    ip_address = Column(String(45))   # IPv4 или IPv6
    user_agent = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)  # = created_at + JWT_REFRESH_TTL_SECONDS
    is_revoked = Column(Boolean, default=False)    # True после logout или ротации

    user = relationship("User", back_populates="sessions")
