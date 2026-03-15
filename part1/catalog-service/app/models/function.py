from __future__ import annotations
from typing import Any, Literal
from pydantic import Field, BaseModel
import uuid
from beanie import Document


class FunctionRequirement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    type: str = "functional"


class AcceptanceCriteria(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str


class TestParams(BaseModel):
    approach: Literal["manual", "automated", "mixed"] = "manual"
    criteria: list[AcceptanceCriteria] = Field(default_factory=list)
    test_data: str | None = None
    expected_result: str | None = None


class CostParams(BaseModel):
    labor_hours: float = 0.0
    rate_per_hour: float | None = None
    complexity_coeff: float = 1.0
    overhead_coeff: float = 1.15


class DocRefs(BaseModel):
    tz_section: str | None = None
    chtz_section: str | None = None
    pmi_test_ids: list[str] = Field(default_factory=list)
    nmck_row: str | None = None


class Function(Document):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    project_id: str
    subsystem_id: str | None = None
    code: str
    name: str
    category: Literal[
        "security", "data_management", "reporting", "integration", "ui", "administration"
    ] = "data_management"
    priority: Literal["must", "should", "could", "wont"] = "should"
    status: Literal["draft", "active", "deprecated", "deleted"] = "draft"

    description: str = ""
    requirements: list[FunctionRequirement] = Field(default_factory=list)
    input_data: str = ""
    output_data: str = ""
    constraints: str = ""
    dependencies: list[str] = Field(default_factory=list)
    complexity: Literal["low", "medium", "high", "critical"] = "medium"

    cost_params: CostParams = Field(default_factory=CostParams)
    test_params: TestParams = Field(default_factory=TestParams)
    doc_refs: DocRefs = Field(default_factory=DocRefs)
    tags: list[str] = Field(default_factory=list)

    version: int = 1
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    class Settings:
        name = "functions"
