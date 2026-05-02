"""
Pytest-обёртка над eval-suite.

Offline evals (без LLM) включены в основной CI — они детерминированы и быстры.
Live/pipeline evals помечены @pytest.mark.live и пропускаются если нет Ollama.
"""

import pytest

from evals.fixtures import EVAL_CASES, SAMPLE_TEST_PLANS, SAMPLE_STEP_RESULTS, EvalCase
from evals.metrics import (
    planner_schema_score,
    gost_coverage_score,
    criteria_coverage_score,
    action_diversity_score,
    steps_count_score,
    planner_total_score,
    writer_schema_score,
    verdict_consistency_score,
    verdict_validity_score,
    writer_total_score,
    pipeline_success_rate,
    pipeline_fallback_rate,
)


# ─── Метрики планировщика ────────────────────────────────────────────────────

class TestPlannerMetrics:

    def test_schema_score_full(self):
        """Хороший план → schema_score == 1.0."""
        plan = SAMPLE_TEST_PLANS["good_plan"]
        assert planner_schema_score(plan) == 1.0

    def test_schema_score_empty(self):
        assert planner_schema_score({}) == 0.0

    def test_schema_score_partial(self):
        plan = {"function_id": "F-1", "function_name": "Test"}
        score = planner_schema_score(plan)
        assert 0.0 < score < 1.0

    def test_gost_coverage_full(self):
        plan = SAMPLE_TEST_PLANS["good_plan"]
        assert gost_coverage_score(plan) == 1.0

    def test_gost_coverage_none(self):
        plan = SAMPLE_TEST_PLANS["no_gost_plan"]
        assert gost_coverage_score(plan) == 0.0

    def test_criteria_coverage_no_criteria(self):
        """Без критериев — 1.0 (нечего покрывать)."""
        plan = SAMPLE_TEST_PLANS["good_plan"]
        assert criteria_coverage_score(plan, []) == 1.0

    def test_criteria_coverage_matched(self):
        plan = SAMPLE_TEST_PLANS["good_plan"]
        criteria = ["Успешный вход перенаправляет на /dashboard", "Форма имеет поля email"]
        score = criteria_coverage_score(plan, criteria)
        assert score > 0.5, f"Ожидалось >0.5, получено {score}"

    def test_action_diversity_good_plan(self):
        plan = SAMPLE_TEST_PLANS["good_plan"]
        # navigate, fill, click, assert → 4 разных action
        score = action_diversity_score(plan)
        assert score == 1.0

    def test_action_diversity_minimal(self):
        plan = SAMPLE_TEST_PLANS["minimal_plan"]
        # только navigate → 1 action
        score = action_diversity_score(plan)
        assert score < 0.5

    def test_steps_count_reasonable(self):
        plan = SAMPLE_TEST_PLANS["good_plan"]  # 4 шага
        assert steps_count_score(plan, min_steps=2) == 1.0

    def test_steps_count_too_few(self):
        plan = SAMPLE_TEST_PLANS["minimal_plan"]  # 1 шаг, min=2
        assert steps_count_score(plan, min_steps=2) < 1.0

    def test_total_score_good_plan(self):
        plan = SAMPLE_TEST_PLANS["good_plan"]
        criteria = ["Успешный вход перенаправляет на /dashboard"]
        result = planner_total_score(plan, criteria)
        assert result["total"] >= 0.70, f"Хороший план должен набирать ≥0.70, получено {result['total']}"

    def test_total_score_no_gost(self):
        plan = SAMPLE_TEST_PLANS["no_gost_plan"]
        result = planner_total_score(plan, ["Проверить функцию"])
        # Штраф за отсутствие ГОСТ-ссылок
        assert result["scores"]["gost"] == 0.0

    def test_all_eval_cases_have_valid_structure(self):
        """Все fixtures корректно описаны."""
        for case in EVAL_CASES:
            assert case.function_id
            assert case.function_name
            assert case.min_steps >= 1


# ─── Метрики протоколиста ────────────────────────────────────────────────────

class TestWriterMetrics:

    def _make_section(self, verdict: str, obs: str = "x" * 80,
                      defects: list | None = None) -> dict:
        return {
            "function_id": "F-1",
            "function_name": "Тест",
            "verdict": verdict,
            "observations": obs,
            "defects": defects or [],
            "recommendation": "Рекомендация",
        }

    def test_schema_full(self):
        section = self._make_section("соответствует")
        assert writer_schema_score(section) == 1.0

    def test_schema_missing_fields(self):
        section = {"function_id": "F-1", "verdict": "соответствует"}
        assert writer_schema_score(section) < 1.0

    def test_verdict_valid(self):
        for v in ("соответствует", "не соответствует", "соответствует частично",
                  "испытание не проводилось"):
            assert verdict_validity_score({"verdict": v}) == 1.0

    def test_verdict_invalid(self):
        assert verdict_validity_score({"verdict": "неизвестно"}) == 0.0

    def test_verdict_consistency_all_passed(self):
        results = SAMPLE_STEP_RESULTS["all_passed"]
        section = self._make_section("соответствует")
        assert verdict_consistency_score(section, results) == 1.0

    def test_verdict_consistency_all_failed(self):
        results = SAMPLE_STEP_RESULTS["all_failed"]
        section = self._make_section("не соответствует")
        assert verdict_consistency_score(section, results) == 1.0

    def test_verdict_consistency_wrong_all_passed(self):
        """Все прошли но вердикт "не соответствует" → 0.0."""
        results = SAMPLE_STEP_RESULTS["all_passed"]
        section = self._make_section("не соответствует")
        assert verdict_consistency_score(section, results) == 0.0

    def test_verdict_consistency_draft_mode(self):
        """Черновой режим (пустые results) → ожидается 'испытание не проводилось'."""
        section = self._make_section("испытание не проводилось")
        assert verdict_consistency_score(section, []) == 1.0

    def test_verdict_consistency_wrong_draft(self):
        section = self._make_section("соответствует")
        assert verdict_consistency_score(section, []) == 0.0

    def test_total_score_all_passed(self):
        results = SAMPLE_STEP_RESULTS["all_passed"]
        section = self._make_section("соответствует")
        result = writer_total_score(section, results)
        assert result["total"] >= 0.70

    def test_total_score_all_failed_with_defects(self):
        results = SAMPLE_STEP_RESULTS["all_failed"]
        section = self._make_section(
            "не соответствует",
            defects=["Element not found", "Timeout"]
        )
        result = writer_total_score(section, results)
        assert result["total"] >= 0.65


# ─── Pipeline-метрики ────────────────────────────────────────────────────────

class TestPipelineMetrics:

    def _make_run(self, status: str, fallback: bool = False) -> dict:
        return {
            "status": status,
            "test_plan": {"_fallback": True} if fallback else {},
            "pmi_section": None,
            "step_results": [],
            "error": None,
        }

    def test_success_rate_all_done(self):
        runs = [self._make_run("done") for _ in range(5)]
        assert pipeline_success_rate(runs) == 1.0

    def test_success_rate_mixed(self):
        runs = [self._make_run("done")] * 3 + [self._make_run("failed")] * 2
        assert pipeline_success_rate(runs) == 0.6

    def test_success_rate_empty(self):
        assert pipeline_success_rate([]) == 0.0

    def test_fallback_rate_none(self):
        runs = [self._make_run("done", fallback=False) for _ in range(4)]
        assert pipeline_fallback_rate(runs) == 0.0

    def test_fallback_rate_all(self):
        runs = [self._make_run("done", fallback=True) for _ in range(4)]
        assert pipeline_fallback_rate(runs) == 1.0


# ─── Offline planner eval (end-to-end fixture check) ─────────────────────────

class TestOfflineEval:

    def test_offline_eval_runs_without_error(self):
        from evals.eval_planner import run_offline_evals
        results = run_offline_evals()
        assert len(results) == 3

    def test_good_plan_passes(self):
        from evals.eval_planner import offline_eval_plan
        case = next(c for c in EVAL_CASES if c.id == "auth-login")
        result = offline_eval_plan(case, SAMPLE_TEST_PLANS["good_plan"])
        assert result.passed(), f"Хороший план должен проходить eval, score={result.total_score}"

    def test_no_gost_plan_has_low_gost_score(self):
        from evals.eval_planner import offline_eval_plan
        case = EvalCase(
            id="no-gost",
            function_id="F-TEST-88",
            function_name="Без ГОСТ",
            function_description="Тест",
            acceptance_criteria=["Проверить"],
        )
        result = offline_eval_plan(case, SAMPLE_TEST_PLANS["no_gost_plan"])
        assert result.gost_score == 0.0


# ─── Live evals (пропускаются без Ollama) ─────────────────────────────────────

@pytest.mark.live
class TestLiveEvals:
    """
    Запускаются только при наличии Ollama.
    Запуск: pytest -m live tests/test_evals.py
    """

    @pytest.mark.asyncio
    async def test_live_planner_auth_login(self):
        from evals.eval_planner import live_eval_plan
        case = next(c for c in EVAL_CASES if c.id == "auth-login")
        result = await live_eval_plan(case)
        assert result.error is None, f"Планировщик вернул ошибку: {result.error}"
        assert result.total_score >= 0.50, f"Ожидалось ≥0.50, получено {result.total_score}"

    @pytest.mark.asyncio
    async def test_live_writer_all_passed(self):
        from evals.eval_writer import _eval_scenario
        result = await _eval_scenario("all_passed", SAMPLE_STEP_RESULTS["all_passed"])
        assert result.error is None
        assert result.verdict_consistency >= 0.8

    @pytest.mark.asyncio
    async def test_live_pipeline_success_rate(self):
        from evals.eval_pipeline import run_pipeline_evals
        # Берём только 2 кейса чтобы не тратить много времени в тестах
        cases = EVAL_CASES[:2]
        result = await run_pipeline_evals(cases=cases, use_mock_executor=True)
        assert result.success_rate >= 0.80, f"success_rate={result.success_rate}"
