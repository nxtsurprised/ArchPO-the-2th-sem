from __future__ import annotations
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import verify_internal_secret
from app.models.audit import AuditLog
from app.services.document_service import get_document, get_render_bundle, list_documents
from app.services.function_service import list_functions

router = APIRouter(tags=["internal"])


@router.get(
    "/internal/documents/{doc_id}/render-bundle",
    dependencies=[Depends(verify_internal_secret)],
)
async def render_bundle(doc_id: str):
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Document not found"})
    bundle = await get_render_bundle(doc)
    return bundle


@router.get(
    "/internal/pmi-functions",
    dependencies=[Depends(verify_internal_secret)],
)
async def get_pmi_functions(project_id: str = Query(...)):
    """Return all active functions for a project — used by pmi-agent."""
    items, _ = await list_functions(project_id=project_id, per_page=1000)
    return {
        "items": [
            {
                "id": fn.id,
                "code": fn.code,
                "name": fn.name,
                "description": fn.description,
                "acceptance_criteria": [c.text for c in fn.test_params.criteria],
                "requirements": [r.text for r in fn.requirements],
            }
            for fn in items
        ]
    }


class PMIResultsRequest(BaseModel):
    sections: dict[str, Any]  # {function_id: pmi_section_dict}


@router.put(
    "/internal/documents/{doc_id}/pmi-results",
    dependencies=[Depends(verify_internal_secret)],
)
async def save_pmi_results(doc_id: str, body: PMIResultsRequest):
    """Write PMI agent results back into a document's data.sections."""
    doc = await get_document(doc_id)
    if not doc:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Document not found"})

    existing_data = doc.data or {}
    existing_sections = existing_data.get("sections", {})
    # Мержим в существующие результаты — чтобы повторный вызов для одной функции
    # не затирал уже сохранённые результаты других функций
    existing_pmi = existing_sections.get("pmi_results", {})
    existing_pmi.update(body.sections)
    existing_sections["pmi_results"] = existing_pmi
    doc.data = {**existing_data, "sections": existing_sections}
    await doc.save()
    return {"ok": True, "saved_functions": list(body.sections.keys())}


@router.get(
    "/internal/tz-context",
    dependencies=[Depends(verify_internal_secret)],
)
async def get_tz_context(project_id: str = Query(...)):
    """
    Возвращает текстовый контекст из ТЗ и ЧТЗ проекта для PMI-агента.
    Ищет утверждённые документы, при отсутствии — берёт последние черновики.
    Возвращает секции в виде читаемого текста.
    """
    # Ищем ТЗ и ЧТЗ документы проекта
    docs, _ = await list_documents(project_id=project_id, per_page=100)
    tz_docs = [d for d in docs if d.type in ("tz", "chtz")]

    if not tz_docs:
        return {"context": "", "documents": []}

    # Приоритет: approved → revision → pending → draft
    STATUS_PRIORITY = {"approved": 0, "revision": 1, "pending": 2, "draft": 3, "rejected": 4}
    tz_docs.sort(key=lambda d: (STATUS_PRIORITY.get(d.status, 9), d.type != "tz"))

    context_parts: list[str] = []
    doc_refs: list[dict] = []

    for doc in tz_docs:
        sections = (doc.data or {}).get("sections", {})
        if not sections:
            continue

        type_label = "Техническое задание" if doc.type == "tz" else "Частное техническое задание"
        status_label = f"статус: {doc.status}"
        header = f"=== {type_label}: «{doc.name}» ({status_label}) ==="
        content_lines = [header]

        for section_key, section_value in sections.items():
            if not section_value:
                continue
            # Вложенные поля (dict) — разворачиваем
            if isinstance(section_value, dict):
                for field_key, field_value in section_value.items():
                    if field_value:
                        content_lines.append(f"[{section_key}.{field_key}]: {field_value}")
            elif isinstance(section_value, list):
                if section_value:
                    content_lines.append(f"[{section_key}]: {'; '.join(str(v) for v in section_value)}")
            else:
                content_lines.append(f"[{section_key}]: {section_value}")

        if len(content_lines) > 1:  # есть содержимое кроме заголовка
            context_parts.append("\n".join(content_lines))
            doc_refs.append({"id": doc.id, "type": doc.type, "name": doc.name, "status": doc.status})

    return {
        "context": "\n\n".join(context_parts),
        "documents": doc_refs,
    }


@router.get(
    "/internal/audit",
    dependencies=[Depends(verify_internal_secret)],
)
async def internal_audit(
    project_id: str | None = Query(None),
    user_id: str | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if user_id:
        query["user_id"] = user_id
    if from_dt:
        query["timestamp"] = {"$gte": from_dt.isoformat()}
    if to_dt:
        existing = query.get("timestamp", {})
        existing["$lte"] = to_dt.isoformat()
        query["timestamp"] = existing

    entries = await AuditLog.find(query).sort("-timestamp").limit(1000).to_list()
    return {
        "items": [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "user_id": e.user_id,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "project_id": e.project_id,
                "result": e.result,
            }
            for e in entries
        ]
    }
