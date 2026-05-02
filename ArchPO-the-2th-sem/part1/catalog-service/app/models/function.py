"""
Модель функции системы — единица справочника функций.

Функция — центральный объект данных всей системы.
Единожды описанная функция используется во всех типах документов:
  - ТЗ (section 4.2): заголовок + описание + требования
  - ЧТЗ: детализация требований
  - ПМИ: test_params — критерии приёмки и тестовые данные
  - НМЦК: cost_params — трудозатраты и коэффициенты для расчёта стоимости

Структура из 4 блоков:
  Информационный блок  — description, requirements, input/output, constraints
  Стоимостной блок     — CostParams (labor_hours, rate, коэффициенты)
  Тестовый блок        — TestParams (критерии приёмки, тестовые данные)
  Ссылки на документы  — DocRefs (разделы ТЗ/ЧТЗ, тесты ПМИ)

Итоговая стоимость функции НЕ хранится — вычисляется XlsxBuilder
по формуле: labor_hours × rate_per_hour × complexity_coeff × overhead_coeff.
Это позволяет менять ставки (Rates) и пересчитывать НМЦК без изменения функций.
"""
from __future__ import annotations
from typing import Any, Literal
from pydantic import Field, BaseModel
import uuid
from beanie import Document


class FunctionRequirement(BaseModel):
    """Атомарное требование к функции (входит в numbered list в ТЗ)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    type: str = "functional"  # functional | non_functional | security


class AcceptanceCriteria(BaseModel):
    """Критерий приёмки для ПМИ — проверяемое условие завершения теста."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str


class TestParams(BaseModel):
    """Параметры тестирования функции (используется в ПМИ)."""
    approach: Literal["manual", "automated", "mixed"] = "manual"
    criteria: list[AcceptanceCriteria] = Field(default_factory=list)
    test_data: str | None = None       # входные данные теста
    expected_result: str | None = None # ожидаемый результат


class CostParams(BaseModel):
    """
    Параметры для расчёта стоимости функции в НМЦК.

    rate_per_hour=None означает «использовать ставку из Rates проекта».
    Итоговая стоимость НЕ хранится здесь — рассчитывается при генерации .xlsx.
    """
    labor_hours: float = 0.0
    rate_per_hour: float | None = None  # None → брать из Rates.default_rate_per_hour
    complexity_coeff: float = 1.0
    overhead_coeff: float = 1.15


class DocRefs(BaseModel):
    """
    Ссылки функции на разделы сгенерированных документов.

    Заполняются generation-service после успешной генерации .docx:
    PATCH /internal/functions/batch-update-refs устанавливает tz_section.
    Это позволяет в Catalog UI показывать «эта функция описана в разделе 4.2.1».
    """
    tz_section: str | None = None     # например "4.2.1"
    chtz_section: str | None = None   # например "3.1"
    pmi_test_ids: list[str] = Field(default_factory=list)  # ID тестов в ПМИ
    nmck_row: str | None = None       # номер строки в НМЦК .xlsx


class Function(Document):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    project_id: str
    subsystem_id: str | None = None   # группировка в разделе 4.2 ТЗ
    code: str                          # человекочитаемый шифр, например "ФБ-03"
    name: str
    category: Literal["main", "auxiliary", "service"] = "main"
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["draft", "active", "deprecated", "deleted"] = "draft"

    # ── Информационный блок ────────────────────────────────────────────────────
    description: str = ""
    requirements: list[FunctionRequirement] = Field(default_factory=list)
    input_data: str = ""
    output_data: str = ""
    constraints: str = ""
    dependencies: list[str] = Field(default_factory=list)  # ID других функций
    complexity: Literal["low", "medium", "high", "critical"] = "medium"

    # ── Остальные блоки ────────────────────────────────────────────────────────
    cost_params: CostParams = Field(default_factory=CostParams)
    test_params: TestParams = Field(default_factory=TestParams)
    doc_refs: DocRefs = Field(default_factory=DocRefs)
    tags: list[str] = Field(default_factory=list)

    version: int = 1
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""

    class Settings:
        name = "functions"   # имя коллекции в MongoDB
