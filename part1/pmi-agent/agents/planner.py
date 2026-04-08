"""
Агент 1 — Планировщик (Planner).
Генерирует тест-план из описания функции с помощью LLM + RAG.
При ошибке LLM: до 2 ретраев с упрощённым промптом, затем детерминированный fallback.
"""

import json
import re

import structlog
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from memory.rag import RAGRetriever
from schemas.state import PMIAgentState

logger = structlog.get_logger(__name__)

_llm: ChatOllama | None = None
_rag: RAGRetriever | None = None

MAX_RETRIES = 2


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.1,
            format="json",
            timeout=settings.ollama_timeout,
        )
    return _llm


def _get_rag() -> RAGRetriever:
    global _rag
    if _rag is None:
        _rag = RAGRetriever(n_results=2)  # меньше контекста — меньше confusion у Mistral
    return _rag


def _load_system_prompt(rag_context: str) -> str:
    from pathlib import Path
    prompt_path = Path(__file__).parent.parent / "prompts" / "planner_system.md"
    template = prompt_path.read_text(encoding="utf-8")
    return template.replace("{rag_context}", rag_context)


def _extract_json(text: str) -> dict:
    """Извлечь JSON из ответа LLM."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Не удалось извлечь JSON: {text[:200]}")


def _unwrap(plan_dict: dict) -> dict:
    """Mistral иногда оборачивает ответ в {"test_plan": {...}} и т.п."""
    for key in ("test_plan", "plan", "result", "output", "response"):
        if key in plan_dict and isinstance(plan_dict[key], dict):
            return plan_dict[key]
    return plan_dict


def _build_human_message(state: PMIAgentState, attempt: int) -> str:
    """Формирует human-сообщение; при ретраях упрощаем до минимума."""
    criteria = "\n".join(f"- {c}" for c in state.get("acceptance_criteria", []))

    if attempt == 0:
        return (
            f"Сгенерируй тест-план в формате JSON.\n\n"
            f"Входные данные:\n"
            f"- function_id: {state['function_id']}\n"
            f"- function_name: {state['function_name']}\n"
            f"- description: {state['function_description']}\n"
            f"- acceptance_criteria:\n{criteria}\n\n"
            f"Обязательные поля в ответе: function_id, function_name, objective, "
            f"preconditions, steps, postconditions, gost_method.\n"
            f"Поле steps — массив объектов: "
            f"step_number, action, description, target, input_data, expected_result, gost_ref."
        )
    else:
        # Упрощённый промпт для ретрая — только самое важное
        return (
            f"Return a JSON test plan for: {state['function_name']} ({state['function_id']}).\n"
            f"Description: {state['function_description']}\n\n"
            f"The JSON MUST have a 'steps' array. Each step: "
            f"step_number(int), action(navigate/click/fill/assert), "
            f"description(str), target(str), input_data(str or null), "
            f"expected_result(str), gost_ref(str or null).\n"
            f"Also include: function_id, function_name, objective, "
            f"preconditions(array), postconditions(array), gost_method(str)."
        )


def _fallback_test_plan(state: PMIAgentState) -> dict:
    """
    Детерминированный тест-план когда LLM не справляется.
    Строится на основе типа функции и acceptance_criteria.
    Всегда содержит валидные steps — пайплайн гарантированно дойдёт до Writer.
    """
    fid = state["function_id"]
    fname = state["function_name"]
    desc = state["function_description"]
    criteria = state.get("acceptance_criteria", [])
    target_url = state.get("target_url", "")

    steps = [
        {
            "step_number": 1,
            "action": "navigate",
            "description": f"Открыть целевую страницу системы",
            "target": target_url or "/",
            "input_data": None,
            "expected_result": "Страница загружена без ошибок",
            "gost_ref": "п. 5.1 ГОСТ 34.603",
        },
        {
            "step_number": 2,
            "action": "screenshot",
            "description": f"Зафиксировать начальное состояние интерфейса для функции: {fname}",
            "target": None,
            "input_data": None,
            "expected_result": "Скриншот сохранён",
            "gost_ref": "п. 5.2 ГОСТ 34.603",
        },
    ]

    # Добавляем assert-шаги из acceptance_criteria
    for idx, criterion in enumerate(criteria, start=3):
        steps.append({
            "step_number": idx,
            "action": "assert",
            "description": f"Проверить критерий: {criterion}",
            "target": "url",
            "input_data": None,
            "expected_result": criterion,
            "gost_ref": "п. 5.3 ГОСТ 34.603",
        })

    if not criteria:
        steps.append({
            "step_number": 3,
            "action": "assert",
            "description": f"Проверить корректность работы функции: {fname}",
            "target": "url",
            "input_data": None,
            "expected_result": "Функция работает без ошибок",
            "gost_ref": "п. 5.3 ГОСТ 34.603",
        })

    return {
        "function_id": fid,
        "function_name": fname,
        "objective": f"Проверить функцию '{fname}' на соответствие требованиям ТЗ",
        "preconditions": ["Система запущена и доступна", "Пользователь имеет доступ к интерфейсу"],
        "steps": steps,
        "postconditions": ["Результаты испытания зафиксированы"],
        "gost_method": "Проверка",
        "_fallback": True,  # маркер что план сгенерирован без LLM
    }


async def _invoke_llm(system_prompt: str, human_text: str) -> dict:
    """Один вызов LLM с извлечением и валидацией JSON."""
    llm = _get_llm()
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_text),
    ])
    logger.debug("planner_llm_raw", response=response.content[:500])
    plan_dict = _extract_json(response.content)
    plan_dict = _unwrap(plan_dict)

    if "steps" not in plan_dict or not isinstance(plan_dict["steps"], list):
        logger.warning(
            "planner_no_steps",
            keys=list(plan_dict.keys()),
            response=response.content[:200],
        )
        raise ValueError(f"Нет поля 'steps'. Ключи: {list(plan_dict.keys())}")

    if len(plan_dict["steps"]) == 0:
        raise ValueError("Поле 'steps' пустое")

    return plan_dict


async def planner_node(state: PMIAgentState) -> dict:
    """
    LangGraph-узел Планировщика.
    Стратегия: до MAX_RETRIES попыток с LLM, затем детерминированный fallback.
    """
    logger.info(
        "planner_start",
        function_id=state["function_id"],
        function_name=state["function_name"],
    )

    rag = _get_rag()
    rag_context = rag.retrieve_for_planner(
        f"{state['function_name']}: {state['function_description']}"
    )
    system_prompt = _load_system_prompt(rag_context)

    last_error: str = ""
    for attempt in range(MAX_RETRIES):
        try:
            human_text = _build_human_message(state, attempt)
            plan_dict = await _invoke_llm(system_prompt, human_text)

            logger.info(
                "planner_done",
                function_id=state["function_id"],
                steps_count=len(plan_dict["steps"]),
                attempt=attempt,
            )
            return {
                "test_plan": plan_dict,
                "current_step": 0,
                "status": "executing",
                "rag_context": rag_context,
            }

        except Exception as e:
            last_error = str(e)
            logger.warning(
                "planner_retry",
                function_id=state["function_id"],
                attempt=attempt,
                error=last_error,
            )

    # Все попытки исчерпаны — используем детерминированный fallback
    logger.warning(
        "planner_fallback",
        function_id=state["function_id"],
        llm_error=last_error,
    )
    plan_dict = _fallback_test_plan(state)
    return {
        "test_plan": plan_dict,
        "current_step": 0,
        "status": "executing",
        "rag_context": rag_context,
    }
