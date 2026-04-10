"""HTTP client for catalog-service internal API."""
from __future__ import annotations

import httpx
import structlog
from typing import Any

from config import settings

logger = structlog.get_logger(__name__)

_HEADERS = {"X-Internal-Secret": settings.internal_api_secret}
_TIMEOUT = 15.0
_TZ_CONTEXT_MAX_CHARS = 3000  # ~750 токенов — комфортно для Mistral 7B


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


async def get_tz_context(project_id: str) -> str:
    """
    Получить текстовый контекст из ТЗ/ЧТЗ проекта.
    Возвращает пустую строку если документов нет или они пустые.
    """
    url = f"{settings.catalog_service_url}/internal/tz-context"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params={"project_id": project_id}, headers=_HEADERS)
            resp.raise_for_status()
            data = resp.json()
            ctx = data.get("context", "")
            docs = data.get("documents", [])
            if len(ctx) > _TZ_CONTEXT_MAX_CHARS:
                ctx = ctx[:_TZ_CONTEXT_MAX_CHARS] + "\n[...контекст усечён]"
            logger.info("tz_context_loaded", project_id=project_id,
                        chars=len(ctx), documents=[d["name"] for d in docs])
            return ctx
    except Exception as exc:
        # Не прерываем работу агента если контекст недоступен
        logger.warning("tz_context_failed", project_id=project_id, error=str(exc))
        return ""


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
