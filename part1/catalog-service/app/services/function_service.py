from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from app.models.function import Function, CostParams, TestParams, DocRefs
from app.schemas.function import FunctionCreate, FunctionUpdate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def list_functions(
    project_id: str | None = None,
    category: str | None = None,
    subsystem_id: str | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Function], int]:
    query: dict[str, Any] = {"status": {"$ne": "deleted"}}
    if project_id:
        query["project_id"] = project_id
    if category:
        query["category"] = category
    if subsystem_id:
        query["subsystem_id"] = subsystem_id
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"code": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    total = await Function.find(query).count()
    items = await Function.find(query).skip((page - 1) * per_page).limit(per_page).to_list()
    return items, total


async def get_function(function_id: str) -> Function | None:
    fn = await Function.get(function_id)
    if fn and fn.status == "deleted":
        return None
    return fn


async def create_function(data: FunctionCreate, created_by: str) -> Function:
    now = _now()
    fn = Function(
        project_id=data.project_id,
        subsystem_id=data.subsystem_id,
        code=data.code,
        name=data.name,
        category=data.category,
        priority=data.priority,
        status="draft",
        description=data.description,
        requirements=[r.model_dump() for r in data.requirements],
        input_data=data.input_data,
        output_data=data.output_data,
        constraints=data.constraints,
        dependencies=data.dependencies,
        complexity=data.complexity,
        cost_params=CostParams(**data.cost_params.model_dump()),
        test_params=TestParams(**data.test_params.model_dump()),
        doc_refs=DocRefs(**data.doc_refs.model_dump()),
        tags=data.tags,
        version=1,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    await fn.insert()
    return fn


async def update_function(fn: Function, data: FunctionUpdate) -> Function:
    updates: dict[str, Any] = {"version": fn.version + 1, "updated_at": _now()}
    for field in (
        "subsystem_id", "name", "category", "description", "requirements",
        "input_data", "output_data", "constraints", "dependencies", "tags",
    ):
        val = getattr(data, field)
        if val is not None:
            if field == "requirements":
                updates[field] = [r.model_dump() for r in val]
            else:
                updates[field] = val
    if data.doc_refs is not None:
        updates["doc_refs"] = data.doc_refs.model_dump()
    if data.test_params is not None:
        updates["test_params"] = data.test_params.model_dump()
    if data.priority is not None:
        updates["priority"] = data.priority
    if data.complexity is not None:
        updates["complexity"] = data.complexity
    if data.cost_params is not None:
        updates["cost_params"] = data.cost_params.model_dump()
    await fn.set(updates)
    return fn


async def soft_delete_function(fn: Function) -> Function:
    await fn.set({"status": "deleted", "updated_at": _now()})
    return fn
