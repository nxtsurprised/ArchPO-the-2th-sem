from __future__ import annotations
from pydantic import Field
import uuid
from beanie import Document


class Subsystem(Document):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    project_id: str
    code: str
    name: str
    description: str = ""
    order: int = 0
    tz_section_prefix: str = ""

    created_at: str = ""
    updated_at: str = ""

    class Settings:
        name = "subsystems"
