"""
Тесты для PMI Agent — проверяют логику агентов без LLM и браузера (mock).
"""

import json
import pytest

from schemas.test_plan import TestStep, StepStatus, StepResult
from schemas.pmi import PMISection


# ─── Тесты схем ──────────────────────────────────────────────────────────

class TestSchemas:
    def test_test_step_valid(self):
        step = TestStep(
            step_number=1,
            action="navigate",
            description="Перейти на страницу входа",
            target="/login",
            expected_result="Отображается форма входа",
        )
        assert step.step_number == 1
        assert step.action == "navigate"

    def test_step_result_passed(self):
        result = StepResult(
            step_number=1,
            status=StepStatus.PASSED,
            actual_result="Страница загружена",
        )
        assert result.status == StepStatus.PASSED

    def test_pmi_section_pass_rate(self):
        section = PMISection(
            function_id="F-AUTH-02",
            function_name="Аутентификация",
            test_objective="Проверить вход",
            verdict="соответствует",
            observations="Функция работает корректно.",
            steps_total=6,
            steps_passed=6,
            steps_failed=0,
        )
        assert section.pass_rate == 1.0

    def test_pmi_section_partial_pass(self):
        section = PMISection(
            function_id="F-AUTH-02",
            function_name="Аутентификация",
            test_objective="Проверить вход",
            verdict="соответствует частично",
            observations="Есть замечания.",
            steps_total=6,
            steps_passed=5,
            steps_failed=1,
        )
        assert round(section.pass_rate, 2) == round(5 / 6, 2)


# ─── Тесты memory/rag (без ChromaDB) ─────────────────────────────────────

class TestChunking:
    def test_chunk_text_basic(self):
        from memory.knowledge_loader import _chunk_text

        text = "Абзац один.\n\nАбзац два.\n\nАбзац три."
        chunks = _chunk_text(text, size=50, overlap=10)
        assert len(chunks) >= 1
        # Каждый чанк не длиннее size
        for chunk in chunks:
            assert len(chunk) <= 60  # небольшой допуск из-за overlap

    def test_chunk_empty_text(self):
        from memory.knowledge_loader import _chunk_text
        assert _chunk_text("") == []

    def test_chunk_preserves_content(self):
        from memory.knowledge_loader import _chunk_text

        text = "Слово " * 200  # длинный текст
        chunks = _chunk_text(text, size=100, overlap=20)
        # Все слова присутствуют в чанках
        full_text = " ".join(chunks)
        assert "Слово" in full_text


# ─── Тесты оркестратора ───────────────────────────────────────────────────

class TestOrchestrator:
    def test_graph_builds(self):
        """Граф должен компилироваться без ошибок."""
        from orchestrator import build_graph
        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_planner_node_mock(self, monkeypatch):
        """Планировщик должен вернуть test_plan при успешном ответе LLM."""
        mock_plan = {
            "function_id": "F-TEST-01",
            "function_name": "Тест",
            "objective": "Проверить",
            "preconditions": [],
            "steps": [
                {
                    "step_number": 1,
                    "action": "navigate",
                    "description": "Открыть",
                    "target": "/",
                    "input_data": None,
                    "expected_result": "Загружено",
                    "gost_ref": None,
                }
            ],
            "postconditions": [],
            "gost_method": "Проверка",
        }

        # Мокаем LLM
        class MockLLM:
            async def ainvoke(self, messages):
                class R:
                    content = json.dumps(mock_plan)
                return R()

        monkeypatch.setattr("agents.planner._get_llm", lambda: MockLLM())

        # Мокаем RAG
        class MockRAG:
            def retrieve_for_planner(self, desc):
                return ""

        monkeypatch.setattr("agents.planner._get_rag", lambda: MockRAG())

        from agents.planner import planner_node

        state = {
            "function_id": "F-TEST-01",
            "function_name": "Тест",
            "function_description": "Описание",
            "acceptance_criteria": [],
            "project_id": "proj-1",
            "target_url": "http://localhost:8080",
            "test_plan": None,
            "current_step": 0,
            "step_results": [],
            "pmi_section": None,
            "status": "planning",
            "error": None,
            "iteration_count": 0,
            "rag_context": None,
        }

        result = await planner_node(state)
        assert result["status"] == "executing"
        assert result["test_plan"]["function_id"] == "F-TEST-01"
        assert len(result["test_plan"]["steps"]) == 1


# ─── Тесты writer fallback ────────────────────────────────────────────────

class TestWriterFallback:
    @pytest.mark.asyncio
    async def test_writer_fallback_on_llm_error(self, monkeypatch):
        """Writer должен вернуть fallback-секцию при ошибке LLM."""

        class FailingLLM:
            async def ainvoke(self, messages):
                raise RuntimeError("LLM недоступен")

        monkeypatch.setattr("agents.writer._get_llm", lambda: FailingLLM())

        class MockRAG:
            def retrieve_for_writer(self, name):
                return ""

        monkeypatch.setattr("agents.writer._get_rag", lambda: MockRAG())

        from agents.writer import writer_node

        state = {
            "function_id": "F-TEST-01",
            "function_name": "Тест функция",
            "function_description": "Описание",
            "acceptance_criteria": [],
            "project_id": "proj-1",
            "target_url": "http://localhost:8080",
            "test_plan": {
                "gost_method": "Проверка",
                "objective": "Проверить",
                "steps": [{"step_number": 1}],
            },
            "current_step": 1,
            "step_results": [
                {"step_number": 1, "status": "passed", "actual_result": "OK"}
            ],
            "pmi_section": None,
            "status": "writing",
            "error": None,
            "iteration_count": 0,
            "rag_context": None,
        }

        result = await writer_node(state)

        assert result["status"] == "done"
        assert result["pmi_section"] is not None
        assert result["pmi_section"]["verdict"] == "соответствует"
        assert result["pmi_section"]["steps_passed"] == 1
