"""
Агент 1 — Планировщик (Planner).
Генерирует тест-план из описания функции с помощью LLM + RAG.
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


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.1,       # Низкая температура — детерминированные JSON
            format="json",         # Ollama JSON mode
            timeout=settings.ollama_timeout,
        )
    return _llm


def _get_rag() -> RAGRetriever:
    global _rag
    if _rag is None:
        _rag = RAGRetriever(n_results=4)
    return _rag


def _load_system_prompt(rag_context: str) -> str:
    from pathlib import Path
    prompt_path = Path(__file__).parent.parent / "prompts" / "planner_system.md"
    template = prompt_path.read_text(encoding="utf-8")
    return template.replace("{rag_context}", rag_context)


def _extract_json(text: str) -> dict:
    """Извлечь JSON из ответа LLM (с или без markdown-блоков)."""
    # Попытка 1: прямой парсинг
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Попытка 2: вырезать ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Попытка 3: найти первый { ... } блок
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Не удалось извлечь JSON из ответа LLM: {text[:200]}")


async def planner_node(state: PMIAgentState) -> dict:
    """
    LangGraph-узел Планировщика.
    Вход: function_id, function_name, function_description, acceptance_criteria
    Выход: обновление поля test_plan в state
    """
    logger.info(
        "planner_start",
        function_id=state["function_id"],
        function_name=state["function_name"],
    )

    # Получаем RAG-контекст
    rag = _get_rag()
    rag_context = rag.retrieve_for_planner(
        f"{state['function_name']}: {state['function_description']}"
    )

    # Формируем промпт
    system_prompt = _load_system_prompt(rag_context)

    human_text = (
        f"Функция: {state['function_name']} (ID: {state['function_id']})\n\n"
        f"Описание: {state['function_description']}\n\n"
        f"Критерии приемки:\n"
        + "\n".join(f"- {c}" for c in state.get("acceptance_criteria", []))
    )

    try:
        llm = _get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_text),
        ])

        plan_dict = _extract_json(response.content)

        # Валидируем базовую структуру
        if "steps" not in plan_dict or not isinstance(plan_dict["steps"], list):
            raise ValueError("Тест-план не содержит поля 'steps'")

        logger.info(
            "planner_done",
            function_id=state["function_id"],
            steps_count=len(plan_dict["steps"]),
        )

        return {
            "test_plan": plan_dict,
            "current_step": 0,
            "status": "executing",
            "rag_context": rag_context,
        }

    except Exception as e:
        logger.error("planner_failed", function_id=state["function_id"], error=str(e))
        return {
            "status": "failed",
            "error": f"Планировщик: {e}",
        }
