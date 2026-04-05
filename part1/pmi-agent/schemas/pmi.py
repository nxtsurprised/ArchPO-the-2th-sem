from datetime import datetime
from pydantic import BaseModel, Field
from .test_plan import StepStatus


class PMIVerdict(str):
    PASSED = "соответствует"
    FAILED = "не соответствует"
    PARTIAL = "соответствует частично"


class PMISection(BaseModel):
    """
    Раздел ПМИ для одной функции по ГОСТ 34.603.
    Соответствует строке/блоку таблицы в разделе «Результаты испытаний».
    """

    function_id: str
    function_name: str
    test_objective: str
    method: str = Field(default="Проверка")
    gost_ref: str = Field(default="ГОСТ 34.603-92")

    # Заполняется Исполнителем
    steps_total: int = 0
    steps_passed: int = 0
    steps_failed: int = 0

    # Формируется Протоколистом
    verdict: str = Field(
        ...,
        description="соответствует | не соответствует | соответствует частично"
    )
    observations: str = Field(
        ...,
        description="Текст наблюдений — что было проверено, что обнаружено"
    )
    defects: list[str] = Field(
        default_factory=list,
        description="Перечень выявленных несоответствий"
    )
    recommendation: str | None = Field(
        None,
        description="Рекомендация: допустить к опытной эксплуатации / устранить замечания"
    )

    @property
    def pass_rate(self) -> float:
        if self.steps_total == 0:
            return 0.0
        return self.steps_passed / self.steps_total


class PMIDocument(BaseModel):
    """Полный документ ПМИ, объединяющий разделы по всем функциям."""

    document_id: str
    project_id: str
    system_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    tester_name: str = Field(default="PMI Agent (автоматический)")
    sections: list[PMISection] = Field(default_factory=list)
    overall_verdict: str | None = None
    docx_path: str | None = None

    def compute_overall_verdict(self) -> str:
        if not self.sections:
            return "не определён"
        failed = [s for s in self.sections if s.verdict == "не соответствует"]
        partial = [s for s in self.sections if s.verdict == "соответствует частично"]
        if failed:
            return "не соответствует"
        if partial:
            return "соответствует частично"
        return "соответствует"
