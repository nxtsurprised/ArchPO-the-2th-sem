"""HTTP client for catalog-service internal API."""
from __future__ import annotations

import httpx
import structlog
from typing import Any

from config import settings

logger = structlog.get_logger(__name__)

_HEADERS = {"X-Internal-Secret": settings.internal_api_secret}
_TIMEOUT = 15.0


async def get_project_functions(project_id: str) -> list[dict]:
    """Fetch all functions for a project from catalog-service internal API."""
    url = f"{settings.catalog_service_url}/internal/pmi-functions"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params={"project_id": project_id}, headers=_HEADERS)
            resp.raise_for_status()
            return resp.json().get("items", [])
    except Exception as exc:
        logger.error("catalog_get_functions_failed", project_id=project_id, error=str(exc))
        raise


async def save_pmi_results(document_id: str, sections: dict[str, Any]) -> None:
    """Write PMI results back to the document in catalog-service."""
    url = f"{settings.catalog_service_url}/internal/documents/{document_id}/pmi-results"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.put(url, json={"sections": sections}, headers=_HEADERS)
            resp.raise_for_status()
        logger.info("pmi_results_saved", document_id=document_id, functions=len(sections))
    except Exception as exc:
        logger.error("catalog_save_results_failed", document_id=document_id, error=str(exc))
        raise
