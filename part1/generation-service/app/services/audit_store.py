from __future__ import annotations
from datetime import datetime, timezone

# In-memory аудит-лог. В production — Kafka / Audit Service.
# Хранится в модуле без зависимости от fastapi, поэтому
# может безопасно импортироваться из сервисного слоя.
_audit_log: list[dict] = []


def record_audit(action: str, **kwargs) -> None:
    _audit_log.append({
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    })


def get_audit_log() -> list[dict]:
    return _audit_log
