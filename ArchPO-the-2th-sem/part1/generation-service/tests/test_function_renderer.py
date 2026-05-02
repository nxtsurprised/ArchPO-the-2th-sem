"""Unit-тесты render_functions."""
from __future__ import annotations
import pytest

from app.pipeline.renderers.function_renderer import render_functions
from app.pipeline.renderers.manual_renderer import IRHeading, IRParagraph, IRList


SECTION = {
    "number": "4.2",
    "title": "Требования к функциям (задачам)",
    "source": "functions",
}

SUBSYSTEMS = [
    {"id": "sub-1", "name": "Подсистема ИБ", "order": 1},
    {"id": "sub-2", "name": "Подсистема АДМ", "order": 2},
]

FUNCTIONS = [
    {
        "id": "f1",
        "subsystem_id": "sub-1",
        "code": "ФБ-01",
        "name": "Аутентификация",
        "description": "Многофакторная аутентификация.",
        "requirements": [
            {"id": "r1", "text": "Поддержка логина и пароля"},
            {"id": "r2", "text": "Политика паролей"},
        ],
        "constraints": "Не более 5 попыток.",
    },
    {
        "id": "f2",
        "subsystem_id": "sub-1",
        "code": "ФБ-02",
        "name": "Журналирование",
        "description": "Ведение журнала действий.",
        "requirements": [],
        "constraints": "",
    },
    {
        "id": "f3",
        "subsystem_id": "sub-2",
        "code": "АД-01",
        "name": "Управление пользователями",
        "description": "CRUD пользователей.",
        "requirements": [{"id": "r3", "text": "Создание, изменение, удаление"}],
        "constraints": "",
    },
]


def test_section_heading_emitted():
    elements = render_functions(SECTION, FUNCTIONS, SUBSYSTEMS)
    assert any(isinstance(e, IRHeading) and "4.2" in e.text for e in elements)


def test_subsystem_headings_ordered():
    elements = render_functions(SECTION, FUNCTIONS, SUBSYSTEMS)
    headings = [e for e in elements if isinstance(e, IRHeading) and e.level == 3]
    assert len(headings) == 2
    assert "Подсистема ИБ" in headings[0].text
    assert "Подсистема АДМ" in headings[1].text


def test_function_headings_emitted():
    elements = render_functions(SECTION, FUNCTIONS, SUBSYSTEMS)
    h4s = [e for e in elements if isinstance(e, IRHeading) and e.level == 4]
    codes = [h.text for h in h4s]
    assert any("ФБ-01" in c for c in codes)
    assert any("ФБ-02" in c for c in codes)
    assert any("АД-01" in c for c in codes)


def test_description_emitted():
    elements = render_functions(SECTION, FUNCTIONS, SUBSYSTEMS)
    paragraphs = [e for e in elements if isinstance(e, IRParagraph)]
    texts = " ".join(p.text for p in paragraphs)
    assert "Многофакторная аутентификация" in texts


def test_requirements_as_numbered_list():
    elements = render_functions(SECTION, FUNCTIONS, SUBSYSTEMS)
    lists = [e for e in elements if isinstance(e, IRList) and e.ordered]
    assert len(lists) >= 1
    flat_items = [item for lst in lists for item in lst.items]
    assert any("логина и пароля" in item for item in flat_items)


def test_constraints_emitted():
    elements = render_functions(SECTION, FUNCTIONS, SUBSYSTEMS)
    paragraphs = [e for e in elements if isinstance(e, IRParagraph)]
    assert any("Ограничения" in p.text for p in paragraphs)


def test_empty_constraints_not_emitted():
    elements = render_functions(SECTION, FUNCTIONS, SUBSYSTEMS)
    paragraphs = [e for e in elements if isinstance(e, IRParagraph)]
    # ФБ-02 имеет пустые constraints — не должно быть лишнего абзаца "Ограничения: "
    ogranicheniya_paragraphs = [p for p in paragraphs if p.text.startswith("Ограничения")]
    assert len(ogranicheniya_paragraphs) == 1  # только для ФБ-01


def test_no_functions_returns_only_section_heading():
    elements = render_functions(SECTION, [], [])
    assert len(elements) == 1
    assert isinstance(elements[0], IRHeading)


def test_functions_no_requirements_no_list():
    funcs = [
        {
            "id": "f99",
            "subsystem_id": "sub-1",
            "code": "XX-01",
            "name": "Без требований",
            "description": "Описание.",
            "requirements": [],
            "constraints": "",
        }
    ]
    elements = render_functions(SECTION, funcs, SUBSYSTEMS[:1])
    lists = [e for e in elements if isinstance(e, IRList)]
    assert len(lists) == 0


def test_real_bundle_functions_render(render_bundle_fixture):
    """Проверяем что реальная фикстура рендерится без исключений."""
    section = next(
        s for s in render_bundle_fixture["template"]["sections"] if s["source"] == "functions"
    )
    functions = render_bundle_fixture["functions"]
    subsystems = render_bundle_fixture["subsystems"]
    elements = render_functions(section, functions, subsystems)
    assert len(elements) > 1
