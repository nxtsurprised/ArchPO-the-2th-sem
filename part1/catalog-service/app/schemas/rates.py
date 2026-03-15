from __future__ import annotations
from pydantic import BaseModel


class RatesUpdate(BaseModel):
    default_rate_per_hour: float | None = None
    complexity_coefficients: dict[str, float] | None = None
    overhead_coefficient: float | None = None
    vat_rate: float | None = None
    profit_margin: float | None = None


class RatesResponse(BaseModel):
    id: str
    project_id: str
    default_rate_per_hour: float
    complexity_coefficients: dict[str, float]
    overhead_coefficient: float
    vat_rate: float
    profit_margin: float
    updated_by: str
    updated_at: str
