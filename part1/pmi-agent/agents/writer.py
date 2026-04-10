"""
Агент 3 — Протоколист (Writer).
По результатам Исполнителя формирует раздел ПМИ согласно ГОСТ 34.603.
"""

import json
import re

import structlog
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from memory.rag import RAGRetriever
from schemas.state import PMIAgentState
from schemas.test_plan import StepStatus

logger = structlog.get_logger(__name__)

_llm: ChatOllama | None = None
_rag: RAGRetriever | None = None


def _get_llm() -> ChatOllama:
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.2,  # Чуть больше вариативности для текста наблюдений
            format="json",
            timeout=settings.ollama_timeout,
        )
    return _llm


def _get_rag() -> RAGRetriever:
    global _rag
    if _rag is None:
        _rag = RAGRetriever(n_results=2)
    return _rag


def _load_system_prompt(rag_context: str) -> str:
    from pathlib import Path
    prompt_path = Path(__file__).parent.parent / "prompts" / "writer_system.md"
    template = prompt_path.read_text(encoding="utf-8")
    return template.replace("{rag_context}", rag_context)


_RU_KEY_MAP = {
    # Вердикт / результат
    "вердикт": "verdict",
    "результат": "verdict",
    "итог": "verdict",
    # Наблюдения
    "наблюдения": "observations",
    "описание": "observations",
    "комментарии": "observations",
    # Дефекты
    "дефекты": "defects",
    "ошибки": "defects",
    "замечания": "defects",
    # Рекомендации
    "рекомендации": "recommendation",
    "рекомендация": "recommendation",
    # Цель
    "цель": "test_objective",
    "цель_теста": "test_objective",
    "цель испытания": "test_objective",
    # Метод
    "метод": "method",
    "метод_испытания": "method",
    # Ссылка на ГОСТ
    "гост": "gost_ref",
    "ссылка_на_гост": "gost_ref",
    "нормативный_документ": "gost_ref",
}

_REQUIRED_KEYS = {"verdict", "observations", "defects", "recommendation"}


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


def _normalize_keys(d: dict) -> dict:
    """Приводит русские ключи к английским эквивалентам (in-place copy)."""
    result = {}
    for k, v in d.items():
        normalized = _RU_KEY_MAP.get(k.lower().strip(), k)
        result[normalized] = v
    return result


def _unwrap_section(raw: dict) -> dict:
    """
    Разворачивает вложенный dict если LLM обернул раздел ПМИ в
    {"Протокол тестирования": {...}} или {"ПМИ": {...}} и т.п.
    Затем нормализует русские ключи → английские.
    """
    d = raw
    # До 2 уровней вложенности
    for _ in range(2):
        # Если уже есть хоть один из ожидаемых ключей — готово
        if _REQUIRED_KEYS & set(d.keys()):
            break
        # Ищем единственный dict-value (обёртка)
        dict_values = [(k, v) for k, v in d.items() if isinstance(v, dict)]
        if len(dict_values) == 1:
            d = dict_values[0][1]
        else:
            break
    return _normalize_keys(d)


def _count_results(step_results: list[dict]) -> tuple[int, int, int]:
    """Возвращает (total, passed, failed)."""
    total = len(step_results)
    passed = sum(1 for r in step_results if r.get("status") == StepStatus.PASSED)
    failed = total - passed
    return total, passed, failed


def _summarize_steps(
    steps: list[dict],
    results: list[dict],
) -> str:
    """Формирует краткое текстовое описание шагов и результатов для промпта LLM."""
    lines: list[str] = []
    result_by_step = {r["step_number"]: r for r in results}

    for step in steps:
        num = step["step_number"]
        result = result_by_step.get(num, {})
        status = result.get("status", "skipped")
        actual = result.get("actual_result", "—")
        expected = step.get("expected_result", "—")

        lines.append(
            f"Шаг {num}: {step.get('description', '')} | "
            f"Ожидалось: {expected} | "
            f"Фактически: {actual} | "
            f"Статус: {status}"
        )

    return "\n".join(lines)


def _build_draft_section(state: PMIAgentState) -> dict:
    """
    Формирует раздел ПМИ в режиме черновика (без фактического выполнения тестов).
    Описывает методику и ожидаемые результаты на основе тест-плана.
    """
    test_plan = state.get("test_plan", {}) or {}
    steps = test_plan.get("steps", [])
    scenarios = []
    for step in steps:
        scenarios.append(
            f"Шаг {step.get('step_number', '?')}: {step.get('description', '')} → "
            f"ожидается: {step.get('expected_result', '')} [{step.get('gost_ref', '')}]"
        )

    return {
        "function_id": state["function_id"],
        "function_name": state["function_name"],
        "test_objective": test_plan.get("objective", f"Проверить функцию '{state['function_name']}'"),
        "method": test_plan.get("gost_method", "Проверка"),
        "gost_ref": "ГОСТ 34.603-92",
        "preconditions": test_plan.get("preconditions", []),
        "postconditions": test_plan.get("postconditions", []),
        "scenarios": scenarios,
        "steps_total": len(steps),
        "steps_passed": None,
        "steps_failed": None,
        "verdict": "испытание не проводилось",
        "observations": (
            f"Методика испытания сформирована автоматически на основе справочника функций. "
            f"Запланировано {len(steps)} шагов проверки. "
            f"Фактическое выполнение не проводилось — документ является черновиком ПМИ."
        ),
        "defects": [],
        "recommendation": "Провести испытание согласно данной методике и зафиксировать фактические результаты.",
        "_draft": True,
    }


async def writer_node(state: PMIAgentState) -> dict:
    """
    LangGraph-узел Протоколиста.
    Вход: test_plan + step_results
    Выход: обновление поля pmi_section в state
    """
    # Режим черновика — не было выполнения тестов, только план
    if state.get("draft_mode"):
        section = _build_draft_section(state)
        logger.info("writer_draft_done", function_id=state["function_id"], steps=section["steps_total"])
        return {"pmi_section": section, "status": "done"}

    test_plan = state.get("test_plan", {})
    step_results = state.get("step_results", [])

    logger.info(
        "writer_start",
        function_id=state["function_id"],
        steps_total=len(step_results),
    )

    # Считаем статистику
    total, passed, failed = _count_results(step_results)

    # RAG-контекст
    rag = _get_rag()
    rag_context = rag.retrieve_for_writer(state["function_name"])
    system_prompt = _load_system_prompt(rag_context)

    # Формируем суммаризацию результатов для промпта
    steps_summary = _summarize_steps(
        test_plan.get("steps", []),
        step_results,
    )

    human_text = (
        f"Функция: {state['function_name']} (ID: {state['function_id']})\n"
        f"Описание: {state['function_description']}\n"
        f"Метод испытания: {test_plan.get('gost_method', 'Проверка')}\n\n"
        f"Результаты выполнения шагов ({total} шагов, {passed} прошли, {failed} провалились):\n\n"
        f"{steps_summary}\n\n"
        f"Составь раздел ПМИ."
    )

    try:
        llm = _get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_text),
        ])

        section_dict = _unwrap_section(_extract_json(response.content))

        # Дополняем статистикой (не доверяем LLM считать)
        section_dict.update({
            "function_id": state["function_id"],
            "function_name": state["function_name"],
            "steps_total": total,
            "steps_passed": passed,
            "steps_failed": failed,
        })

        logger.info(
            "writer_done",
            function_id=state["function_id"],
            verdict=section_dict.get("verdict"),
        )

        return {
            "pmi_section": section_dict,
            "status": "done",
        }

    except Exception as e:
        logger.error("writer_failed", function_id=state["function_id"], error=str(e))

        # Fallback: формируем раздел ПМИ без LLM на основе статистики
        fallback_section = {
            "function_id": state["function_id"],
            "function_name": state["function_name"],
            "test_objective": test_plan.get("objective", ""),
            "method": test_plan.get("gost_method", "Проверка"),
            "gost_ref": "ГОСТ 34.603-92",
            "steps_total": total,
            "steps_passed": passed,
            "steps_failed": failed,
            "verdict": "соответствует" if failed == 0 else "не соответствует",
            "observations": (
                f"В ходе испытания функции '{state['function_name']}' выполнено {total} шагов. "
                f"Успешно: {passed}, с ошибками: {failed}."
            ),
            "defects": [
                r.get("error_message", "Неизвестная ошибка")
                for r in step_results
                if r.get("status") != StepStatus.PASSED
            ],
            "recommendation": (
                "Функция допускается к опытной эксплуатации."
                if failed == 0
                else "Требуется доработка."
            ),
        }

        return {
            "pmi_section": fallback_section,
            "status": "done",
            "error": f"LLM Протоколиста недоступен, использован fallback: {e}",
        }
