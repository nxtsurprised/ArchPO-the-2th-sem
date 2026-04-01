from __future__ import annotations
"""
Notifies Catalog Service when a document should be locked/unlocked.

In MVP: fire-and-forget HTTP PATCH.
In tests: patched out entirely.
If Catalog returns non-2xx or is unavailable, we log and continue —
the lock state in Workflow is authoritative.
"""
import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger()


async def notify_catalog_lock(document_id: str, locked: bool, status: str) -> None:
    """
    Tell Catalog to update document status and lock flag.

    document_id: Catalog document ID string.
    locked: True to block editing, False to allow.
    status: new document status ("draft" | "pending" | "approved" | "rejected").
    """
    settings = get_settings()
    url = f"{settings.CATALOG_INTERNAL_URL}/internal/documents/{document_id}/status"
    payload = {"status": status, "locked": locked}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.patch(
                url,
                json=payload,
                headers={"X-Internal-Secret": settings.INTERNAL_API_SECRET},
            )
            if resp.status_code >= 400:
                logger.warning(
                    "catalog_lock_non2xx",
                    document_id=document_id,
                    status_code=resp.status_code,
                )
    except Exception as exc:
        logger.warning("catalog_lock_failed", document_id=document_id, error=str(exc))
