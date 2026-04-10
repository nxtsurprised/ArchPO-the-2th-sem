"""
Evals для Планировщика (Planner).

Два режима:
1. offline_eval — оценивает готовые тест-планы из fixtures без вызова LLM.
2. live_eval    — вызывает реальный LLM-планировщик и оценивает его выход.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from evals.fixtures import EVAL_CASES, SAMPLE_TEST_PLANS, EvalCase
from evals.metrics import planner_total_score


@dataclass
class PlannerEvalResult:
    case_id: str
    plan_source: str          # "llm" | "fixture" | "fallback"
    schema_score: float
    steps_score: float
    gost_score: float
    criteria_score: float
    diversity_score: float
    total_score: float
    steps_count: int
    error: str | None = None

    def passed(self, threshold: float = 0.60) -> bool:
        return self.total_score >= threshold

    def summary(self) -> str:
        status = "PASS" if self.passed() else "FAIL"
        return (
            f"[{status}] {self.case_id} | total={self.total_score:.2f} "
            f"(schema={self.schema_score:.2f}, gost={self.gost_score:.2f}, "
            f"criteria={self.criteria_score:.2f}, steps={self.steps_count})"
        )


def offline_eval_plan(case: EvalCase, test_plan: dict) -> PlannerEvalResult:
    """Оценить готовый тест-план без запуска LLM."""
    result = planner_total_score(test_plan, case.acceptance_criteria, case.min_steps)
    s = result["scores"]
    return PlannerEvalResult(
        case_id=case.id,
        plan_source="fixture",
        schema_score=s["schema"],
        steps_score=s["steps"],
        gost_score=s["gost"],
        criteria_score=s["criteria"],
        diversity_score=s["diversity"],
        total_score=result["total"],
        steps_count=len(test_plan.get("steps", [])),
    )


async def live_eval_plan(case: EvalCase) -> PlannerEvalResult:
    """Вызвать реальный Planner-агент и оценить его выход."""
    from agents.planner import planner_node

    state = {
        "function_id": case.function_id,
        "function_name": case.function_name,
        "function_description": case.function_description,
        "acceptance_criteria": case.acceptance_criteria,
        "project_id": "eval-project",
        "target_url": "http://nginx:80",
        "test_plan": None,
        "current_step": 0,
        "step_results": [],
        "pmi_section": None,
        "status": "planning",
        "error": None,
        "iteration_count": 0,
        "rag_context": None,
        "draft_mode": False,
    }

    try:
        output = await planner_node(state)
        plan = output.get("test_plan", {})
        is_fallback = plan.get("_fallback", False)
        result = planner_total_score(plan, case.acceptance_criteria, case.min_steps)
        s = result["scores"]
        return PlannerEvalResult(
            case_id=case.id,
            plan_source="fallback" if is_fallback else "llm",
            schema_score=s["schema"],
            steps_score=s["steps"],
            gost_score=s["gost"],
            criteria_score=s["criteria"],
            diversity_score=s["diversity"],
            total_score=result["total"],
            steps_count=len(plan.get("steps", [])),
        )
    except Exception as e:
        return PlannerEvalResult(
            case_id=case.id,
            plan_source="error",
            schema_score=0.0,
            steps_score=0.0,
            gost_score=0.0,
            criteria_score=0.0,
            diversity_score=0.0,
            total_score=0.0,
            steps_count=0,
            error=str(e),
        )


def run_offline_evals() -> list[PlannerEvalResult]:
    """
    Оффлайн-evals: проверяем известные тест-планы из fixtures.
    Не требует LLM или внешних сервисов — детерминированно.
    """
    results = []

    # good_plan vs auth-login case
    good_case = next(c for c in EVAL_CASES if c.id == "auth-login")
    results.append(offline_eval_plan(good_case, SAMPLE_TEST_PLANS["good_plan"]))

    # minimal_plan — должен пройти с низким но допустимым баллом
    minimal_case = EvalCase(
        id="minimal-case",
        function_id="F-TEST-99",
        function_name="Тест",
        function_description="Проверить что-то",
        acceptance_criteria=[],
        min_steps=1,
    )
    results.append(offline_eval_plan(minimal_case, SAMPLE_TEST_PLANS["minimal_plan"]))

    # no_gost_plan — должен получить низкий gost_score
    no_gost_case = EvalCase(
        id="no-gost-case",
        function_id="F-TEST-88",
        function_name="Без ГОСТ",
        function_description="Тест без ссылок на ГОСТ",
        acceptance_criteria=["Проверить функцию"],
        min_steps=2,
    )
    results.append(offline_eval_plan(no_gost_case, SAMPLE_TEST_PLANS["no_gost_plan"]))

    return results


async def run_live_evals(cases: list[EvalCase] | None = None) -> list[PlannerEvalResult]:
    """Live-evals: вызываем реальный LLM-планировщик."""
    cases = cases or EVAL_CASES
    tasks = [live_eval_plan(case) for case in cases]
    return await asyncio.gather(*tasks)
