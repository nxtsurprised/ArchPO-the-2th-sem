"""
Агент 2 — Исполнитель (Executor).
Выполняет один шаг тест-плана через Playwright + LLM (для поиска селекторов).
"""

import json
import re

import structlog
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from memory.rag import RAGRetriever
from schemas.state import PMIAgentState
from schemas.test_plan import TestStep, StepResult, StepStatus
from tools.browser import BrowserTool

logger = structlog.get_logger(__name__)

_llm: ChatOllama | None = None
_rag: RAGRetriever | None = None

# Реестр браузеров: ключ = function_id (он же session_id).
# LangGraph вызывает executor_node многократно в цикле (по одному шагу за вызов),
# поэтому браузер нельзя создавать и уничтожать на каждой итерации — это дорого.
# Браузер живёт весь пайплайн одной функции и закрывается в _cleanup_node.
_browsers: dict[str, BrowserTool] = {}


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.0,
            format="json",
            timeout=settings.ollama_timeout,
        )
    return _llm


def _get_rag() -> RAGRetriever:
    global _rag
    if _rag is None:
        _rag = RAGRetriever(n_results=3)
    return _rag


def _load_system_prompt(rag_context: str) -> str:
    from pathlib import Path
    prompt_path = Path(__file__).parent.parent / "prompts" / "executor_system.md"
    template = prompt_path.read_text(encoding="utf-8")
    return template.replace("{rag_context}", rag_context)


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Не удалось извлечь JSON: {text[:200]}")


async def _get_or_create_browser(session_id: str) -> BrowserTool:
    """Получить или создать браузер для данной сессии."""
    if session_id not in _browsers:
        browser = BrowserTool()
        await browser.start()
        _browsers[session_id] = browser
    return _browsers[session_id]


async def _resolve_selector(step: TestStep) -> TestStep:
    """
    Если target шага неоднозначен — спросить LLM какой селектор использовать.
    Возвращает step с уточненным target.
    """
    # Если target уже похож на CSS-селектор — не трогаем
    css_indicators = ["[", "#", ".", "input", "button", "select", "a[", "form"]
    target = step.target or ""
    if any(target.startswith(ind) for ind in css_indicators):
        return step

    # Если navigate или api_call — target это URL, не трогаем
    if step.action in ("navigate", "api_call", "screenshot", "assert"):
        return step

    # Иначе — просим LLM
    rag = _get_rag()
    rag_context = rag.retrieve_for_executor(step.description)
    system_prompt = _load_system_prompt(rag_context)

    human_text = json.dumps({
        "action": step.action,
        "description": step.description,
        "target": step.target,
        "expected_result": step.expected_result,
    }, ensure_ascii=False)

    try:
        llm = _get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_text),
        ])
        resolved = _extract_json(response.content)

        # Обновляем step с новым селектором
        updated = step.model_copy(update={"target": resolved.get("selector") or step.target})
        return updated
    except Exception as e:
        logger.warning("selector_resolution_failed", step=step.step_number, error=str(e))
        return step  # Возвращаем оригинал без изменений


async def executor_node(state: PMIAgentState) -> dict:
    """
    LangGraph-узел Исполнителя.
    Выполняет ОДИН шаг тест-плана за каждый вызов.
    Граф вызывает этот узел в цикле (через conditional_edges).
    """
    test_plan = state.get("test_plan")
    if not test_plan or not test_plan.get("steps"):
        return {"status": "failed", "error": "Тест-план пустой или отсутствует"}

    steps = test_plan["steps"]
    current_step_idx = state.get("current_step", 0)

    if current_step_idx >= len(steps):
        # Все шаги выполнены
        return {"status": "writing", "current_step": current_step_idx}

    step_data = steps[current_step_idx]
    step = TestStep(**step_data)

    logger.info(
        "executor_step_start",
        function_id=state["function_id"],
        step=step.step_number,
        action=step.action,
    )

    # Получаем или создаём браузер
    session_id = state["function_id"]
    try:
        browser = await _get_or_create_browser(session_id)

        # Уточняем селектор через LLM если нужно
        step = await _resolve_selector(step)

        # Выполняем шаг
        result: StepResult = await browser.execute_step(step, state["target_url"])

    except Exception as e:
        logger.error("executor_browser_error", step=step.step_number, error=str(e))
        result = StepResult(
            step_number=step.step_number,
            status=StepStatus.FAILED,
            actual_result=f"Ошибка браузера: {e}",
            error_message=str(e),
        )

    logger.info(
        "executor_step_done",
        step=step.step_number,
        status=result.status,
        duration_ms=result.duration_ms,
    )

    return {
        # step_results — список из ОДНОГО элемента, но LangGraph объединяет их через
        # operator.add (объявлен в PMIAgentState): каждый вызов executor_node
        # добавляет элемент к общему списку, не перезаписывает.
        "step_results": [result.model_dump()],
        "current_step": current_step_idx + 1,
        "status": "executing",  # _should_continue_executor решит: ещё шаги или writer
    }


async def cleanup_browser(function_id: str) -> None:
    """Закрыть браузер после завершения тестирования функции."""
    if function_id in _browsers:
        await _browsers[function_id].stop()
        del _browsers[function_id]
