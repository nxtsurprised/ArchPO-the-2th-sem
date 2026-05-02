from __future__ import annotations
from pydantic import Field
import uuid
from beanie import Document


class Rates(Document):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    project_id: str
    default_rate_per_hour: float = 3500.0
    complexity_coefficients: dict[str, float] = Field(
        default_factory=lambda: {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5,
            "critical": 2.0,
        }
    )
    overhead_coefficient: float = 1.15
    vat_rate: float = 0.20
    profit_margin: float = 0.15

    updated_by: str = ""
    updated_at: str = ""

    class Settings:
        name = "rates"
