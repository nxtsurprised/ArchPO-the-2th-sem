from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from app.models.document import Document
from app.models.template import Template
from app.models.function import Function
from app.models.subsystem import Subsystem
from app.models.rates import Rates
from app.schemas.document import DocumentCreate, DocumentUpdate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def list_documents(
    project_id: str | None = None,
    type_filter: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Document], int]:
    query: dict[str, Any] = {}
    if project_id:
        query["project_id"] = project_id
    if type_filter:
        query["type"] = type_filter
    total = await Document.find(query).count()
    items = await Document.find(query).skip((page - 1) * per_page).limit(per_page).to_list()
    return items, total


async def get_document(doc_id: str) -> Document | None:
    return await Document.get(doc_id)


async def create_document(data: DocumentCreate, created_by: str) -> Document:
    now = _now()

    # Предзаполняем секции из шаблона — только manual-поля, пустые значения
    initial_sections: dict[str, Any] = {}
    if data.template_id:
        tmpl = await Template.get(data.template_id)
        if tmpl:
            for section in tmpl.sections:
                if section.get("source") == "manual" and section.get("fields"):
                    sec_num = section["number"]
                    initial_sections[sec_num] = {
                        f["key"]: "" for f in section["fields"]
                    }

    doc = Document(
        project_id=data.project_id,
        template_id=data.template_id,
        name=data.name,
        type=data.type,
        status="draft",
        function_ids=data.function_ids,
        data={"sections": initial_sections},
        version=1,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    await doc.insert()
    return doc


async def update_document(doc: Document, data: DocumentUpdate) -> Document:
    updates: dict[str, Any] = {"version": doc.version + 1, "updated_at": _now()}
    if data.name is not None:
        updates["name"] = data.name
    if data.template_id is not None:
        updates["template_id"] = data.template_id
    if data.function_ids is not None:
        updates["function_ids"] = data.function_ids
    if data.data is not None:
        updates["data"] = data.data
    await doc.set(updates)
    return doc


async def delete_document(doc: Document) -> None:
    await doc.delete()


async def validate_document(doc: Document) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not doc.template_id:
        return {"is_valid": False, "errors": ["template not assigned"], "warnings": []}
    tmpl = await Template.get(doc.template_id)
    if not tmpl:
        return {"is_valid": False, "errors": ["template not found"], "warnings": []}

    sections_data = doc.data.get("sections", {})

    for section in tmpl.sections:
        sec_num = section.get("number", "")
        source = section.get("source", "manual")

        if source == "manual":
            for field in section.get("fields", []):
                if field.get("required") and not sections_data.get(sec_num, {}).get(field["key"]):
                    errors.append(f"section.{sec_num}.{field['key']}: required")

        elif source == "functions":
            if not doc.function_ids:
                warnings.append(f"section.{sec_num}: 0 functions")

    return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings}


async def get_render_bundle(doc: Document) -> dict[str, Any]:
    if not doc.template_id:
        return {}
    tmpl = await Template.get(doc.template_id)
    if not tmpl:
        return {}

    functions = []
    if doc.function_ids:
        for fid in doc.function_ids:
            fn = await Function.get(fid)
            if fn:
                functions.append(fn.model_dump())

    subsystems_raw = await Subsystem.find(
        {"project_id": doc.project_id}
    ).sort("+order").to_list()

    rates_doc = await Rates.find_one({"project_id": doc.project_id})
    rates = rates_doc.model_dump() if rates_doc else {}

    return {
        "template": {
            "sections": tmpl.sections,
            "formatting": tmpl.formatting,
        },
        "dotx_key": tmpl.dotx_file_key,
        "data": doc.data,
        "functions": functions,
        "subsystems": [s.model_dump() for s in subsystems_raw],
        "rates": rates,
        "project": {"id": doc.project_id},
    }
