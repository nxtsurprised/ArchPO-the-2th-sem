"""LangGraph state schema для мультиагентного PMI-пайплайна."""

import operator
from typing import Annotated, TypedDict


class PMIAgentState(TypedDict):
    """
    Общее состояние графа LangGraph.
    Передаётся между узлами: Planner → Executor → Writer.

    Поля с Annotated[list, operator.add] накапливаются (не перезаписываются)
    при каждом обновлении — это стандартный паттерн LangGraph для accumulating state.
    """

    # ─── Входные данные (заполняет вызывающий код) ────────────────────────
    function_id: str
    function_name: str
    function_description: str
    acceptance_criteria: list[str]
    project_id: str
    target_url: str               # URL фронтенда, который тестируем

    # ─── Выход Планировщика ───────────────────────────────────────────────
    test_plan: dict | None        # Сериализованный TestPlan (dict, а не объект)

    # ─── Состояние Исполнителя ────────────────────────────────────────────
    current_step: int             # Индекс текущего шага (0-based)
    step_results: Annotated[list[dict], operator.add]  # Накапливаются результаты шагов

    # ─── Выход Протоколиста ───────────────────────────────────────────────
    pmi_section: dict | None      # Сериализованный PMISection (dict, а не объект)

    # ─── Управление потоком ───────────────────────────────────────────────
    status: str   # planning | executing | writing | done | failed
    error: str | None
    iteration_count: int          # Защита от бесконечных циклов
    rag_context: str | None       # RAG-контекст, подготовленный для текущего узла
    draft_mode: bool              # True → только план+методика, без запуска Playwright
    tz_context: str | None        # Содержимое ТЗ/ЧТЗ проекта для обогащения планировщика
