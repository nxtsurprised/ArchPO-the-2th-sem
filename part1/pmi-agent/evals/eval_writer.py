"""
Evals для Протоколиста (Writer).

Проверяет качество секции ПМИ при разных сценариях результатов:
- все шаги прошли → ожидается вердикт "соответствует"
- все шаги провалились → "не соответствует"
- частичный провал → "соответствует частично"
- черновой режим → "испытание не проводилось"
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from evals.fixtures import SAMPLE_TEST_PLANS, SAMPLE_STEP_RESULTS
from evals.metrics import writer_total_score


@dataclass
class WriterEvalResult:
    scenario: str            # "all_passed" | "all_failed" | "partial" | "draft"
    schema_score: float
    verdict_validity: float
    verdict_consistency: float
    observations_score: float
    defects_score: float
    total_score: float
    verdict_actual: str
    error: str | None = None

    def passed(self, threshold: float = 0.65) -> bool:
        return self.total_score >= threshold

    def summary(self) -> str:
        status = "PASS" if self.passed() else "FAIL"
        return (
            f"[{status}] {self.scenario} | total={self.total_score:.2f} "
            f"verdict='{self.verdict_actual}' "
            f"(schema={self.schema_score:.2f}, consistency={self.verdict_consistency:.2f})"
        )


def _make_writer_state(step_results: list[dict], draft_mode: bool = False) -> dict:
    return {
        "function_id": "F-AUTH-01",
        "function_name": "Аутентификация пользователя",
        "function_description": "Вход в систему по логину и паролю",
        "acceptance_criteria": ["Успешный вход перенаправляет на /dashboard"],
        "project_id": "eval-project",
        "target_url": "http://nginx:80",
        "test_plan": SAMPLE_TEST_PLANS["good_plan"],
        "current_step": len(step_results),
        "step_results": step_results,
        "pmi_section": None,
        "status": "writing",
        "error": None,
        "iteration_count": len(step_results),
        "rag_context": None,
        "draft_mode": draft_mode,
    }


async def _eval_scenario(scenario: str, step_results: list[dict], draft: bool = False) -> WriterEvalResult:
    from agents.writer import writer_node

    state = _make_writer_state(step_results, draft_mode=draft)
    try:
        output = await writer_node(state)
        section = output.get("pmi_section", {}) or {}
        result = writer_total_score(section, step_results)
        s = result["scores"]
        return WriterEvalResult(
            scenario=scenario,
            schema_score=s["schema"],
            verdict_validity=s["verdict_val"],
            verdict_consistency=s["verdict_cons"],
            observations_score=s["observations"],
            defects_score=s["defects"],
            total_score=result["total"],
            verdict_actual=section.get("verdict", ""),
        )
    except Exception as e:
        return WriterEvalResult(
            scenario=scenario,
            schema_score=0.0,
            verdict_validity=0.0,
            verdict_consistency=0.0,
            observations_score=0.0,
            defects_score=0.0,
            total_score=0.0,
            verdict_actual="",
            error=str(e),
        )


async def run_writer_evals() -> list[WriterEvalResult]:
    """
    Запускает writer_node в 4 сценариях и оценивает качество секции ПМИ.
    Требует доступный LLM (или корректно работающий fallback).
    """
    tasks = [
        _eval_scenario("all_passed",  SAMPLE_STEP_RESULTS["all_passed"]),
        _eval_scenario("all_failed",  SAMPLE_STEP_RESULTS["all_failed"]),
        _eval_scenario("partial",     SAMPLE_STEP_RESULTS["partial"]),
        _eval_scenario("draft_mode",  [],  draft=True),
    ]
    return await asyncio.gather(*tasks)
