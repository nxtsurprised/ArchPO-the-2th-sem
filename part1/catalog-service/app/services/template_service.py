from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from app.models.template import Template
from app.schemas.template import TemplateCreate, TemplateUpdate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def list_templates(
    project_id: str | None = None,
    type_filter: str | None = None,
) -> list[Template]:
    query: dict[str, Any] = {}
    if project_id is not None:
        # Include system templates (project_id=null) + project-specific templates
        query = {"$or": [{"project_id": None}, {"project_id": project_id}]}
    if type_filter:
        if "$or" in query:
            for clause in query["$or"]:
                clause["type"] = type_filter
        else:
            query["type"] = type_filter
    return await Template.find(query).to_list()


async def get_template(template_id: str) -> Template | None:
    return await Template.get(template_id)


async def create_template(data: TemplateCreate, created_by: str) -> Template:
    now = _now()
    tmpl = Template(
        type=data.type,
        name=data.name,
        gost_ref=data.gost_ref,
        output_format=data.output_format,
        is_system=False,
        parent_id=data.parent_id,
        project_id=data.project_id,
        dotx_file_key=data.dotx_file_key,
        formatting=data.formatting,
        sections=data.sections,
        version=1,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    await tmpl.insert()
    return tmpl


async def update_template(
    tmpl: Template, data: TemplateUpdate
) -> Template:
    updates: dict[str, Any] = {"version": tmpl.version + 1, "updated_at": _now()}
    if data.name is not None:
        updates["name"] = data.name
    if data.gost_ref is not None:
        updates["gost_ref"] = data.gost_ref
    if data.dotx_file_key is not None:
        updates["dotx_file_key"] = data.dotx_file_key
    if data.formatting is not None:
        updates["formatting"] = data.formatting
    if data.sections is not None:
        updates["sections"] = data.sections
    await tmpl.set(updates)
    return tmpl


async def delete_template(tmpl: Template) -> None:
    await tmpl.delete()
