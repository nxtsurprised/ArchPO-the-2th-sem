from enum import Enum
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TestStep(BaseModel):
    """Один шаг тест-плана, сгенерированный Планировщиком."""

    step_number: int = Field(..., ge=1, description="Порядковый номер шага")
    action: str = Field(..., description="Действие: navigate | click | fill | assert | screenshot | api_call")
    description: str = Field(..., description="Описание шага на русском языке")
    target: str | None = Field(None, description="CSS-селектор, URL или имя элемента")
    input_data: str | None = Field(None, description="Вводимые данные (для fill)")
    expected_result: str = Field(..., description="Ожидаемый результат шага")
    gost_ref: str | None = Field(None, description="Ссылка на пункт ГОСТ 34.603, напр. 'п. 5.4'")


class TestPlan(BaseModel):
    """Полный тест-план для одной функции системы."""

    function_id: str
    function_name: str
    objective: str = Field(..., description="Цель тестирования")
    preconditions: list[str] = Field(default_factory=list)
    steps: list[TestStep]
    postconditions: list[str] = Field(default_factory=list)
    gost_method: str = Field(
        default="Проверка",
        description="Метод испытания по ГОСТ 34.603: Проверка | Демонстрация | Тестирование | Анализ"
    )


class StepResult(BaseModel):
    """Результат выполнения одного шага Исполнителем."""

    step_number: int
    status: StepStatus
    actual_result: str = Field(..., description="Фактический результат наблюдения")
    screenshot_path: str | None = None
    http_response: dict | None = Field(None, description="Перехваченный HTTP-ответ (если есть)")
    dom_snapshot: str | None = Field(None, description="Фрагмент DOM (для ошибок)")
    error_message: str | None = None
    duration_ms: int | None = None
