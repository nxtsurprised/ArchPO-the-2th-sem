"""
Точка запуска eval-suite PMI Agent.

Использование:
    # Только оффлайн (без LLM, быстро):
    python -m evals.run_evals --mode offline

    # С реальным LLM (требует запущенный Ollama):
    python -m evals.run_evals --mode live

    # Полный прогон: planner + writer + pipeline с mock-executor:
    python -m evals.run_evals --mode full

    # JSON-отчёт:
    python -m evals.run_evals --mode full --json

Коды возврата:
    0 — все evals прошли выше порогов
    1 — один или несколько evals провалились
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime


# ─── Цветной вывод ───────────────────────────────────────────────────────────

def _color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"

GREEN  = lambda t: _color(t, "32")
RED    = lambda t: _color(t, "31")
YELLOW = lambda t: _color(t, "33")
BOLD   = lambda t: _color(t, "1")
CYAN   = lambda t: _color(t, "36")


def _hr(char: str = "─", width: int = 70) -> str:
    return char * width


# ─── Offline evals (без LLM) ──────────────────────────────────────────────────

def run_offline(verbose: bool = False) -> tuple[bool, dict]:
    from evals.eval_planner import run_offline_evals

    print(BOLD("\n[OFFLINE] Planner evals (детерминированные, без LLM)"))
    print(_hr())

    results = run_offline_evals()
    passed_all = True

    for r in results:
        print(GREEN(r.summary()) if r.passed() else RED(r.summary()))
        passed_all = passed_all and r.passed()

    # Проверяем ожидаемые свойства конкретных fixtures
    _check_fixture_properties(results)

    return passed_all, {"offline_planner": [vars(r) for r in results]}


def _check_fixture_properties(results: list) -> None:
    """Дополнительные проверки: ожидаемые свойства конкретных fixtures."""
    print(CYAN("\nДополнительные проверки fixtures:"))

    result_map = {r.case_id: r for r in results}

    # good_plan должен получить gost_score = 1.0
    if "auth-login" in result_map:
        r = result_map["auth-login"]
        ok = r.gost_score >= 0.9
        marker = GREEN("✓") if ok else RED("✗")
        print(f"  {marker} auth-login: gost_score={r.gost_score:.2f} (ожидается ≥0.90)")

    # no_gost_plan должен получить низкий gost_score
    if "no-gost-case" in result_map:
        r = result_map["no-gost-case"]
        ok = r.gost_score == 0.0
        marker = GREEN("✓") if ok else RED("✗")
        print(f"  {marker} no-gost-case: gost_score={r.gost_score:.2f} (ожидается 0.00)")


# ─── Live evals (с реальным LLM) ─────────────────────────────────────────────

async def run_live(verbose: bool = False) -> tuple[bool, dict]:
    from evals.eval_planner import run_live_evals, EVAL_CASES
    from evals.eval_writer import run_writer_evals

    print(BOLD("\n[LIVE] Planner evals (реальный LLM)"))
    print(_hr())
    print(YELLOW("  ⚠ Требуется запущенный Ollama + модель mistral:7b-instruct"))

    planner_results = await run_live_evals()
    p_passed = True
    for r in planner_results:
        print(GREEN(r.summary()) if r.passed() else RED(r.summary()))
        if verbose and r.error:
            print(YELLOW(f"    error: {r.error}"))
        p_passed = p_passed and r.passed()

    print(BOLD("\n[LIVE] Writer evals (реальный LLM, 4 сценария)"))
    print(_hr())

    writer_results = await run_writer_evals()
    w_passed = True
    for r in writer_results:
        print(GREEN(r.summary()) if r.passed() else RED(r.summary()))
        w_passed = w_passed and r.passed()

    return p_passed and w_passed, {
        "live_planner": [vars(r) for r in planner_results],
        "live_writer": [vars(r) for r in writer_results],
    }


# ─── Pipeline evals (planner + mock executor + writer) ───────────────────────

async def run_pipeline(verbose: bool = False) -> tuple[bool, dict]:
    from evals.eval_pipeline import run_pipeline_evals

    print(BOLD("\n[PIPELINE] End-to-end evals (mock executor, без Playwright)"))
    print(_hr())

    result = await run_pipeline_evals(use_mock_executor=True)
    print(result.summary())

    if verbose:
        print(CYAN("\nДетали по кейсам:"))
        for r in result.run_details:
            status = GREEN("done") if r["status"] == "done" else RED(r["status"])
            fallback = YELLOW(" [fallback]") if (r.get("test_plan") or {}).get("_fallback") else ""
            print(f"  {r['case_id']}: {status}{fallback} ({r['duration_sec']}s)")
            if r.get("error"):
                print(RED(f"    error: {r['error']}"))

    return result.overall_passed(), {"pipeline": vars(result)}


# ─── Runner ───────────────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> int:
    print(BOLD(f"\n{'='*70}"))
    print(BOLD(f"  PMI Agent Eval Suite  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}"))
    print(BOLD(f"  mode: {args.mode}"))
    print(BOLD(f"{'='*70}"))

    all_passed = True
    report: dict = {"mode": args.mode, "timestamp": datetime.now().isoformat(), "results": {}}

    if args.mode in ("offline", "full"):
        ok, data = run_offline(verbose=args.verbose)
        all_passed = all_passed and ok
        report["results"].update(data)

    if args.mode in ("live", "full"):
        ok, data = await run_live(verbose=args.verbose)
        all_passed = all_passed and ok
        report["results"].update(data)

    if args.mode in ("pipeline", "full"):
        ok, data = await run_pipeline(verbose=args.verbose)
        all_passed = all_passed and ok
        report["results"].update(data)

    # Итог
    print(_hr("═"))
    if all_passed:
        print(GREEN(f"  ✅  Все evals прошли успешно"))
    else:
        print(RED(f"  ❌  Часть evals провалилась — см. детали выше"))

    if args.json:
        print("\n" + json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if all_passed else 1


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="PMI Agent Evaluation Suite",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["offline", "live", "pipeline", "full"],
        default="offline",
        help=(
            "offline  — детерминированные проверки без LLM\n"
            "live     — planner + writer с реальным Ollama\n"
            "pipeline — planner→mock_executor→writer\n"
            "full     — все режимы"
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument("--json", action="store_true", help="Вывести JSON-отчёт")

    args = parser.parse_args()
    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
