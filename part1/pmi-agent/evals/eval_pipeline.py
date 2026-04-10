"""
Evals агентной системы в целом (pipeline-level).

Оценивает:
- success_rate   — % прогонов без ошибок
- fallback_rate  — % прогонов с LLM-fallback (планировщик не справился)
- avg_plan_score — средняя оценка тест-планов
- avg_pmi_score  — средняя оценка секций ПМИ
- avg_duration   — среднее время полного прогона (только с mock executor)

Для запуска без Playwright используется mock-исполнитель.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from evals.fixtures import EVAL_CASES, EvalCase
from evals.metrics import (
    pipeline_success_rate,
    pipeline_fallback_rate,
    avg_planner_score,
    avg_writer_score,
)


@dataclass
class PipelineEvalResult:
    total_runs: int
    success_rate: float
    fallback_rate: float
    avg_plan_score: float
    avg_pmi_score: float
    avg_duration_sec: float
    run_details: list[dict]

    def summary(self) -> str:
        sr_status = "PASS" if self.success_rate >= 0.80 else "FAIL"
        ps_status = "PASS" if self.avg_plan_score >= 0.55 else "FAIL"
        ws_status = "PASS" if self.avg_pmi_score >= 0.55 else "FAIL"
        return (
            f"Pipeline Evals ({self.total_runs} runs)\n"
            f"  [{sr_status}] success_rate   = {self.success_rate:.0%}\n"
            f"  [INFO] fallback_rate  = {self.fallback_rate:.0%}\n"
            f"  [{ps_status}] avg_plan_score = {self.avg_plan_score:.3f}\n"
            f"  [{ws_status}] avg_pmi_score  = {self.avg_pmi_score:.3f}\n"
            f"  [INFO] avg_duration   = {self.avg_duration_sec:.1f}s"
        )

    def overall_passed(self) -> bool:
        return (
            self.success_rate >= 0.80
            and self.avg_plan_score >= 0.55
            and self.avg_pmi_score >= 0.55
        )


async def _mock_executor(state: dict) -> dict:
    """
    Mock-исполнитель для pipeline evals — симулирует выполнение шагов без браузера.
    Все шаги проходят успешно (оптимистичный сценарий).
    Используется чтобы измерить работу Planner+Writer без Playwright.
    """
    test_plan = state.get("test_plan") or {}
    steps = test_plan.get("steps", [])
    results = [
        {
            "step_number": s.get("step_number", i + 1),
            "status": "passed",
            "actual_result": f"[mock] {s.get('expected_result', 'OK')}",
            "error_message": None,
            "duration_ms": 50,
        }
        for i, s in enumerate(steps)
    ]
    return {
        "step_results": results,
        "current_step": len(steps),
        "status": "writing",
    }


async def run_single_case(case: EvalCase, use_mock_executor: bool = True) -> dict:
    """Запустить полный pipeline для одного eval-кейса."""
    from agents.planner import planner_node
    from agents.writer import writer_node

    start = time.time()

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

    run_result = {
        "case_id": case.id,
        "function_id": case.function_id,
        "acceptance_criteria": case.acceptance_criteria,
        "status": "failed",
        "test_plan": None,
        "pmi_section": None,
        "step_results": [],
        "error": None,
        "duration_sec": 0.0,
        "used_mock_executor": use_mock_executor,
    }

    try:
        # 1. Planner
        planner_out = await planner_node(state)
        state.update(planner_out)

        if state.get("status") == "failed":
            run_result["error"] = state.get("error", "Planner failed")
            run_result["duration_sec"] = round(time.time() - start, 2)
            return run_result

        run_result["test_plan"] = state["test_plan"]

        # 2. Executor (mock или пропускаем для draft)
        if use_mock_executor:
            exec_out = await _mock_executor(state)
            state.update(exec_out)
            # LangGraph accumulates step_results, replicate that here
            state["step_results"] = exec_out["step_results"]

        # 3. Writer
        writer_out = await writer_node(state)
        state.update(writer_out)

        run_result.update({
            "status": state.get("status", "done"),
            "pmi_section": state.get("pmi_section"),
            "step_results": state.get("step_results", []),
            "error": state.get("error"),
        })

    except Exception as e:
        run_result["error"] = str(e)

    run_result["duration_sec"] = round(time.time() - start, 2)
    return run_result


async def run_pipeline_evals(
    cases: list[EvalCase] | None = None,
    use_mock_executor: bool = True,
) -> PipelineEvalResult:
    """
    Запускает pipeline eval для каждого кейса и вычисляет агрегированные метрики.

    Args:
        cases: список eval-кейсов (по умолчанию все из fixtures)
        use_mock_executor: если True — Playwright не используется (mock-шаги)
    """
    cases = cases or EVAL_CASES
    run_tasks = [run_single_case(case, use_mock_executor) for case in cases]
    run_details = await asyncio.gather(*run_tasks)

    return PipelineEvalResult(
        total_runs=len(run_details),
        success_rate=pipeline_success_rate(run_details),
        fallback_rate=pipeline_fallback_rate(run_details),
        avg_plan_score=avg_planner_score(run_details),
        avg_pmi_score=avg_writer_score(run_details),
        avg_duration_sec=round(
            sum(r["duration_sec"] for r in run_details) / len(run_details), 2
        ) if run_details else 0.0,
        run_details=list(run_details),
    )
