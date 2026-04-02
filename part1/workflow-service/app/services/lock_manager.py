"""
Notifies Catalog Service when a document should be locked/unlocked.

v2 (current): async Kafka event on topic gost34.workflow.events.
  Catalog consumes the event and updates document status + lock flag.
  Fire-and-forget with graceful fallback — workflow state is authoritative.

v1 (removed): fire-and-forget HTTP PATCH to /internal/documents/{id}/status.
  Replaced because the HTTP endpoint didn't exist and calls were silently failing.
"""
import structlog
from shared.services.events import EventEmitter

logger = structlog.get_logger()
_emitter = EventEmitter(service_name="workflow")


async def notify_catalog_lock(document_id: str, locked: bool, status: str, approval_id: str = "") -> None:
    """
    Emit a document lock/unlock event to Kafka.

    document_id : Catalog document ID.
    locked      : True to block editing, False to allow.
    status      : New document status ("draft"|"pending"|"approved"|"rejected").
    approval_id : The approval request that triggered this change (for tracing).
    """
    event_type = "document.locked" if locked else "document.unlocked"
    await _emitter.emit(
        event_type=event_type,
        payload={
            "document_id": document_id,
            "locked": locked,
            "document_status": status,
            "approval_id": approval_id,
        },
        topic="gost34.workflow.events",
        key=document_id,
    )
    logger.info("lock_event_emitted", document_id=document_id, locked=locked, status=status)
