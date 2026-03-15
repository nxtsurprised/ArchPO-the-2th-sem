from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
import uuid


@dataclass
class Job:
    document_id: str
    format: Literal["docx", "xlsx"]
    requested_by: str  # user_id из JWT

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    progress: int = 0          # 0-100
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    file_key: str | None = None   # путь в MinIO
    checksum: str | None = None   # SHA-256
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "job_id": self.id,
            "document_id": self.document_id,
            "format": self.format,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "file_url": None,  # заполняется отдельно при необходимости
            "checksum": self.checksum,
            "error": self.error,
            "warnings": self.warnings,
        }
