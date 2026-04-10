"""
LangGraph-граф мультиагентной системы PMI.

Поток: START → planner_node → executor_node (цикл) → writer_node → END

Условная логика:
- После executor_node: если current_step < len(steps) → продолжить выполнение
- После executor_node: если current_step >= len(steps) → перейти к writer_node
- Если status == "failed" на любом узле → END (с ошибкой)
- Защита от зацикливания: iteration_count > MAX_ITERATIONS → END
"""

import structlog
from langgraph.graph import StateGraph, END

from agents import planner_node, executor_node, writer_node
from agents.executor import cleanup_browser
from schemas.state import PMIAgentState

logger = structlog.get_logger(__name__)

MAX_ITERATIONS = 50  # Максимум шагов тест-плана


def _should_continue_executor(state: PMIAgentState) -> str:
    """
    Условное ребро после executor_node.
    Возвращает имя следующего узла.
    """
    # Критические ошибки — выход
    if state.get("status") == "failed":
        return "end_failed"

    # Защита от бесконечных циклов
    iteration = state.get("iteration_count", 0) + 1
    if iteration > MAX_ITERATIONS:
        logger.error("max_iterations_exceeded", function_id=state.get("function_id"))
        return "end_failed"

    test_plan = state.get("test_plan") or {}
    steps = test_plan.get("steps", [])
    current_step = state.get("current_step", 0)

    # Все шаги выполнены → Протоколист
    if current_step >= len(steps):
        return "writer"

    # Ещё есть шаги → продолжаем
    return "executor"


async def _increment_iteration(state: PMIAgentState) -> dict:
    """Вспомогательный узел — увеличивает счетчик итераций."""
    return {"iteration_count": state.get("iteration_count", 0) + 1}


async def _cleanup_node(state: PMIAgentState) -> dict:
    """Закрываем браузер после завершения тестирования."""
    function_id = state.get("function_id", "")
    if function_id:
        await cleanup_browser(function_id)
    # LangGraph 0.1.x требует непустой dict — пробрасываем текущий статус
    return {"status": state.get("status", "done")}


def _should_continue_planner(state: PMIAgentState) -> str:
    """Условное ребро после planner — пропускаем executor если планировщик упал."""
    if state.get("status") == "failed":
        return "cleanup"
    return "executor"


def build_graph() -> StateGraph:
    """Собирает LangGraph StateGraph."""
    builder = StateGraph(PMIAgentState)

    # Узлы
    builder.add_node("planner", planner_node)
    builder.add_node("executor", executor_node)
    builder.add_node("writer", writer_node)
    builder.add_node("cleanup", _cleanup_node)

    # Точка входа
    builder.set_entry_point("planner")

    # Условное ребро после planner (если упал — сразу в cleanup)
    builder.add_conditional_edges(
        "planner",
        _should_continue_planner,
        {
            "executor": "executor",
            "cleanup": "cleanup",
        },
    )

    # Условное ребро после executor (цикл или переход к writer)
    builder.add_conditional_edges(
        "executor",
        _should_continue_executor,
        {
            "executor": "executor",       # ещё шаги
            "writer": "writer",           # все шаги выполнены
            "end_failed": "cleanup",      # ошибка
        },
    )

    builder.add_edge("writer", "cleanup")
    builder.add_edge("cleanup", END)

    return builder


# Компилируем граф один раз при импорте модуля
_graph = build_graph().compile()


def build_draft_graph() -> StateGraph:
    """
    Упрощённый граф для режима черновика: START → planner_node → writer_node → END.
    Executor (Playwright) полностью пропускается.
    """
    builder = StateGraph(PMIAgentState)

    builder.add_node("planner", planner_node)
    builder.add_node("writer", writer_node)
    builder.add_node("cleanup", _cleanup_node)

    builder.set_entry_point("planner")

    # После planner: если ошибка → cleanup, иначе → writer
    builder.add_conditional_edges(
        "planner",
        _should_continue_planner,
        {
            "executor": "writer",   # в draft-режиме "executor" редиректим сразу на writer
            "cleanup": "cleanup",
        },
    )

    builder.add_edge("writer", "cleanup")
    builder.add_edge("cleanup", END)

    return builder


_draft_graph = build_draft_graph().compile()


async def run_draft_pipeline(
    function_id: str,
    function_name: str,
    function_description: str,
    acceptance_criteria: list[str],
    project_id: str,
) -> dict:
    """
    Запускает черновой пайплайн: план → методика (без Playwright).

    Returns:
        dict с ключами: status, pmi_section, error, test_plan
    """
    initial_state: PMIAgentState = {
        "function_id": function_id,
        "function_name": function_name,
        "function_description": function_description,
        "acceptance_criteria": acceptance_criteria,
        "project_id": project_id,
        "target_url": "",
        "test_plan": None,
        "current_step": 0,
        "step_results": [],
        "pmi_section": None,
        "status": "planning",
        "error": None,
        "iteration_count": 0,
        "rag_context": None,
        "draft_mode": True,
    }

    logger.info("draft_pipeline_start", function_id=function_id)

    final_state = await _draft_graph.ainvoke(initial_state)

    logger.info(
        "draft_pipeline_done",
        function_id=function_id,
        status=final_state.get("status"),
    )

    return {
        "status": final_state.get("status"),
        "pmi_section": final_state.get("pmi_section"),
        "error": final_state.get("error"),
        "test_plan": final_state.get("test_plan"),
    }


async def run_pmi_pipeline(
    function_id: str,
    function_name: str,
    function_description: str,
    acceptance_criteria: list[str],
    project_id: str,
    target_url: str,
) -> dict:
    """
    Запускает полный пайплайн PMI для одной функции системы.

    Returns:
        dict с ключами:
        - status: "done" | "failed"
        - pmi_section: dict (раздел ПМИ) или None
        - error: str | None
        - step_results: list[dict]
    """
    initial_state: PMIAgentState = {
        "function_id": function_id,
        "function_name": function_name,
        "function_description": function_description,
        "acceptance_criteria": acceptance_criteria,
        "project_id": project_id,
        "target_url": target_url,
        # Поля, заполняемые агентами
        "test_plan": None,
        "current_step": 0,
        "step_results": [],
        "pmi_section": None,
        "status": "planning",
        "error": None,
        "iteration_count": 0,
        "rag_context": None,
    }

    logger.info("pmi_pipeline_start", function_id=function_id)

    final_state = await _graph.ainvoke(initial_state)

    logger.info(
        "pmi_pipeline_done",
        function_id=function_id,
        status=final_state.get("status"),
        verdict=final_state.get("pmi_section", {}).get("verdict") if final_state.get("pmi_section") else None,
    )

    return {
        "status": final_state.get("status"),
        "pmi_section": final_state.get("pmi_section"),
        "error": final_state.get("error"),
        "step_results": final_state.get("step_results", []),
        "test_plan": final_state.get("test_plan"),
    }
