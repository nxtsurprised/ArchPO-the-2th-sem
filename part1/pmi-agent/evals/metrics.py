"""
Метрики качества для оценки выходов LLM-агентов.

Каждая метрика возвращает float в диапазоне [0.0, 1.0].
Метрики не требуют LLM или внешних сервисов — это детерминированные функции.
"""

from __future__ import annotations

import re


# ─── Метрики планировщика ──────────────────────────────────────────────────────

REQUIRED_PLAN_FIELDS = {"function_id", "function_name", "objective", "steps", "gost_method"}
VALID_ACTIONS = {"navigate", "click", "fill", "assert", "screenshot", "wait", "scroll"}


def planner_schema_score(test_plan: dict) -> float:
    """Все обязательные поля тест-плана присутствуют и непустые."""
    if not test_plan:
        return 0.0
    present = sum(
        1 for f in REQUIRED_PLAN_FIELDS
        if f in test_plan and test_plan[f] not in (None, "", [], {})
    )
    return present / len(REQUIRED_PLAN_FIELDS)


def steps_count_score(test_plan: dict, min_steps: int = 2, max_steps: int = 20) -> float:
    """
    Количество шагов в разумном диапазоне.
    Меньше min → штраф, больше max → штраф за избыточность.
    """
    steps = test_plan.get("steps", [])
    n = len(steps)
    if n == 0:
        return 0.0
    if n < min_steps:
        return n / min_steps
    if n > max_steps:
        return max(0.0, 1.0 - (n - max_steps) / max_steps)
    return 1.0


def gost_coverage_score(test_plan: dict) -> float:
    """Доля шагов, у которых заполнено поле gost_ref."""
    steps = test_plan.get("steps", [])
    if not steps:
        return 0.0
    with_gost = sum(1 for s in steps if s.get("gost_ref"))
    return with_gost / len(steps)


def criteria_coverage_score(test_plan: dict, acceptance_criteria: list[str]) -> float:
    """
    Какой процент acceptance criteria упоминается в описаниях/ожидаемых результатах шагов.

    Используется нечёткое совпадение: критерий считается покрытым, если хотя бы
    одно значимое слово из него встречается в тексте шагов.
    """
    if not acceptance_criteria:
        return 1.0  # нет критериев — нечего проверять

    steps = test_plan.get("steps", [])
    if not steps:
        return 0.0

    # Собираем весь текст шагов
    step_text = " ".join(
        (s.get("description", "") + " " + s.get("expected_result", "")).lower()
        for s in steps
    )

    covered = 0
    for criterion in acceptance_criteria:
        # Ключевые слова: слова длиннее 4 символов (исключаем предлоги и союзы)
        keywords = [w.lower() for w in re.split(r"\W+", criterion) if len(w) > 4]
        if not keywords:
            covered += 1  # слишком короткий критерий — засчитываем
            continue
        if any(kw in step_text for kw in keywords):
            covered += 1

    return covered / len(acceptance_criteria)


def action_diversity_score(test_plan: dict) -> float:
    """
    Разнообразие типов action в шагах.
    Хороший тест-план использует минимум 2 разных типа действий.
    """
    steps = test_plan.get("steps", [])
    if not steps:
        return 0.0
    unique_actions = {s.get("action") for s in steps if s.get("action") in VALID_ACTIONS}
    # 1 action → 0.3, 2 → 0.6, 3+ → 1.0
    return min(1.0, len(unique_actions) * 0.35)


def planner_total_score(test_plan: dict, acceptance_criteria: list[str], min_steps: int = 2) -> dict:
    """Агрегированная оценка тест-плана с весами компонент."""
    weights = {
        "schema":    0.30,
        "steps":     0.20,
        "gost":      0.20,
        "criteria":  0.20,
        "diversity": 0.10,
    }
    scores = {
        "schema":    planner_schema_score(test_plan),
        "steps":     steps_count_score(test_plan, min_steps),
        "gost":      gost_coverage_score(test_plan),
        "criteria":  criteria_coverage_score(test_plan, acceptance_criteria),
        "diversity": action_diversity_score(test_plan),
    }
    total = sum(scores[k] * weights[k] for k in weights)
    return {"scores": scores, "weights": weights, "total": round(total, 3)}


# ─── Метрики протоколиста ──────────────────────────────────────────────────────

REQUIRED_SECTION_FIELDS = {"verdict", "observations", "defects", "recommendation"}
VALID_VERDICTS = {"соответствует", "не соответствует", "соответствует частично", "испытание не проводилось"}


def writer_schema_score(section: dict) -> float:
    """Все обязательные поля секции ПМИ присутствуют."""
    if not section:
        return 0.0
    present = sum(
        1 for f in REQUIRED_SECTION_FIELDS
        if f in section and section[f] not in (None, "")
    )
    return present / len(REQUIRED_SECTION_FIELDS)


def verdict_validity_score(section: dict) -> float:
    """Вердикт содержит одно из допустимых значений."""
    verdict = section.get("verdict", "")
    return 1.0 if verdict in VALID_VERDICTS else 0.0


def verdict_consistency_score(section: dict, step_results: list[dict]) -> float:
    """
    Вердикт логически соответствует результатам шагов.

    Правила:
    - 0 failed → должен быть "соответствует"
    - все failed → должен быть "не соответствует"
    - частично → "соответствует частично" или "не соответствует"
    - draft_mode (пустые results) → "испытание не проводилось"
    """
    verdict = section.get("verdict", "")

    if not step_results:
        # Черновой режим — ожидаем "испытание не проводилось"
        return 1.0 if verdict == "испытание не проводилось" else 0.0

    total = len(step_results)
    failed = sum(1 for r in step_results if r.get("status") == "failed")
    pass_rate = (total - failed) / total if total > 0 else 0

    if failed == 0:
        return 1.0 if verdict == "соответствует" else 0.0
    if failed == total:
        return 1.0 if verdict == "не соответствует" else 0.3
    # Частичный провал
    if verdict in ("соответствует частично", "не соответствует"):
        return 1.0
    if verdict == "соответствует":
        # Допускаем если провалилось < 20%
        return 0.5 if pass_rate >= 0.8 else 0.0
    return 0.5


def observations_quality_score(section: dict) -> float:
    """
    Минимальное качество поля observations:
    - длина ≥ 30 символов → 0.5
    - длина ≥ 80 символов → 1.0
    """
    text = section.get("observations", "") or ""
    if len(text) >= 80:
        return 1.0
    if len(text) >= 30:
        return 0.5
    return 0.0


def defects_when_failed_score(section: dict, step_results: list[dict]) -> float:
    """
    Если были провальные шаги, секция должна содержать непустой список дефектов.
    При черновом режиме (нет результатов) — дефектов не должно быть.
    """
    if not step_results:
        # Черновой режим
        defects = section.get("defects", [])
        return 1.0 if not defects else 0.7  # небольшой штраф, не критично

    failed = sum(1 for r in step_results if r.get("status") == "failed")
    defects = section.get("defects", [])

    if failed > 0 and not defects:
        return 0.0  # есть провалы но нет дефектов — плохо
    if failed == 0 and defects:
        return 0.7  # дефекты без провалов — подозрительно
    return 1.0


def writer_total_score(section: dict, step_results: list[dict]) -> dict:
    """Агрегированная оценка секции ПМИ с весами."""
    weights = {
        "schema":       0.25,
        "verdict_val":  0.20,
        "verdict_cons": 0.30,
        "observations": 0.15,
        "defects":      0.10,
    }
    scores = {
        "schema":       writer_schema_score(section),
        "verdict_val":  verdict_validity_score(section),
        "verdict_cons": verdict_consistency_score(section, step_results),
        "observations": observations_quality_score(section),
        "defects":      defects_when_failed_score(section, step_results),
    }
    total = sum(scores[k] * weights[k] for k in weights)
    return {"scores": scores, "weights": weights, "total": round(total, 3)}


# ─── Метрики агентной системы (pipeline-уровень) ──────────────────────────────

def pipeline_success_rate(run_results: list[dict]) -> float:
    """Доля прогонов со status == 'done' (без ошибок)."""
    if not run_results:
        return 0.0
    success = sum(1 for r in run_results if r.get("status") == "done")
    return success / len(run_results)


def pipeline_fallback_rate(run_results: list[dict]) -> float:
    """
    Доля прогонов, где LLM не справился и был использован fallback.
    Определяется по маркеру _fallback в test_plan или ошибке LLM в error.
    """
    if not run_results:
        return 0.0
    fallbacks = sum(
        1 for r in run_results
        if (r.get("test_plan") or {}).get("_fallback")
        or "fallback" in (r.get("error") or "").lower()
    )
    return fallbacks / len(run_results)


def avg_planner_score(run_results: list[dict]) -> float:
    """Средняя оценка тест-планов по всем прогонам."""
    scores = []
    for r in run_results:
        plan = r.get("test_plan")
        criteria = r.get("acceptance_criteria", [])
        if plan:
            s = planner_total_score(plan, criteria)
            scores.append(s["total"])
    return round(sum(scores) / len(scores), 3) if scores else 0.0


def avg_writer_score(run_results: list[dict]) -> float:
    """Средняя оценка секций ПМИ по всем прогонам."""
    scores = []
    for r in run_results:
        section = r.get("pmi_section")
        step_results = r.get("step_results", [])
        if section:
            s = writer_total_score(section, step_results)
            scores.append(s["total"])
    return round(sum(scores) / len(scores), 3) if scores else 0.0
