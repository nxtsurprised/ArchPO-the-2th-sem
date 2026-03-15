from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
import uuid


class RequirementIn(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    type: str = "functional"


class AcceptanceCriteriaIn(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str


class TestParamsIn(BaseModel):
    approach: Literal["manual", "automated", "mixed"] = "manual"
    criteria: list[AcceptanceCriteriaIn] = []
    test_data: str | None = None
    expected_result: str | None = None


class CostParamsIn(BaseModel):
    labor_hours: float = 0.0
    rate_per_hour: float | None = None
    complexity_coeff: float = 1.0
    overhead_coeff: float = 1.15


class DocRefsIn(BaseModel):
    tz_section: str | None = None
    chtz_section: str | None = None
    pmi_test_ids: list[str] = []
    nmck_row: str | None = None


class FunctionCreate(BaseModel):
    project_id: str
    subsystem_id: str | None = None
    code: str
    name: str
    category: Literal[
        "security", "data_management", "reporting", "integration", "ui", "administration"
    ] = "data_management"
    priority: Literal["must", "should", "could", "wont"] = "should"
    description: str = ""
    requirements: list[RequirementIn] = []
    input_data: str = ""
    output_data: str = ""
    constraints: str = ""
    dependencies: list[str] = []
    complexity: Literal["low", "medium", "high", "critical"] = "medium"
    cost_params: CostParamsIn = Field(default_factory=CostParamsIn)
    test_params: TestParamsIn = Field(default_factory=TestParamsIn)
    doc_refs: DocRefsIn = Field(default_factory=DocRefsIn)
    tags: list[str] = []


class FunctionUpdate(BaseModel):
    subsystem_id: str | None = None
    name: str | None = None
    category: Literal[
        "security", "data_management", "reporting", "integration", "ui", "administration"
    ] | None = None
    description: str | None = None
    requirements: list[RequirementIn] | None = None
    input_data: str | None = None
    output_data: str | None = None
    constraints: str | None = None
    dependencies: list[str] | None = None
    tags: list[str] | None = None
    doc_refs: DocRefsIn | None = None
    test_params: TestParamsIn | None = None
    # These fields require pm role:
    priority: Literal["must", "should", "could", "wont"] | None = None
    complexity: Literal["low", "medium", "high", "critical"] | None = None
    cost_params: CostParamsIn | None = None


class FunctionResponse(BaseModel):
    id: str
    project_id: str
    subsystem_id: str | None
    code: str
    name: str
    category: str
    priority: str
    status: str
    description: str
    requirements: list[dict]
    input_data: str
    output_data: str
    constraints: str
    dependencies: list[str]
    complexity: str
    cost_params: dict
    test_params: dict
    doc_refs: dict
    tags: list[str]
    version: int
    created_by: str
    created_at: str
    updated_at: str
