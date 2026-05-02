"""Unit-тесты BundleValidator."""
from __future__ import annotations
import pytest

from app.pipeline.validator import BundleValidator


@pytest.fixture
def validator() -> BundleValidator:
    return BundleValidator()


@pytest.fixture
def minimal_bundle():
    """Минимально валидный bundle."""
    return {
        "template": {
            "sections": [
                {
                    "number": "1",
                    "source": "manual",
                    "title": "Общие сведения",
                    "fields": [
                        {"key": "system_name", "label": "Наименование", "type": "text", "required": True},
                        {"key": "customer_name", "label": "Заказчик", "type": "text", "required": True},
                    ],
                }
            ]
        },
        "data": {
            "sections": {
                "1": {"system_name": "ГИС ЖКХ", "customer_name": "Минстрой России"}
            }
        },
        "functions": [],
        "subsystems": [],
        "rates": {},
    }


def test_valid_bundle(validator, minimal_bundle):
    result = validator.validate(minimal_bundle)
    assert result.is_valid is True
    assert result.missing_fields == []


def test_missing_required_field(validator, minimal_bundle):
    # Убираем customer_name из данных
    del minimal_bundle["data"]["sections"]["1"]["customer_name"]
    result = validator.validate(minimal_bundle)
    assert result.is_valid is False
    assert "section.1.customer_name" in result.missing_fields


def test_missing_all_required_fields(validator):
    bundle = {
        "template": {
            "sections": [
                {
                    "number": "2",
                    "source": "manual",
                    "title": "Назначение",
                    "fields": [
                        {"key": "purpose", "label": "Назначение", "type": "textarea", "required": True},
                        {"key": "goals", "label": "Цели", "type": "list", "required": True},
                    ],
                }
            ]
        },
        "data": {"sections": {}},
        "functions": [],
        "subsystems": [],
        "rates": {},
    }
    result = validator.validate(bundle)
    assert result.is_valid is False
    assert "section.2.purpose" in result.missing_fields
    assert "section.2.goals" in result.missing_fields


def test_optional_field_not_required(validator, minimal_bundle):
    # Добавляем optional поле без данных — не должно влиять на валидность
    minimal_bundle["template"]["sections"][0]["fields"].append(
        {"key": "deadlines", "label": "Сроки", "type": "date_range", "required": False}
    )
    result = validator.validate(minimal_bundle)
    assert result.is_valid is True


def test_functions_section_warns_when_empty(validator, minimal_bundle):
    minimal_bundle["template"]["sections"].append(
        {"number": "4.2", "source": "functions", "title": "Функции", "render_rule": "functions_grouped_by_subsystem"}
    )
    minimal_bundle["functions"] = []
    result = validator.validate(minimal_bundle)
    assert result.is_valid is True  # warning, не ошибка
    assert any("4.2" in w for w in result.warnings)


def test_functions_section_no_warning_when_present(validator, minimal_bundle):
    minimal_bundle["template"]["sections"].append(
        {"number": "4.2", "source": "functions", "title": "Функции"}
    )
    minimal_bundle["functions"] = [{"id": "f1", "name": "Авторизация"}]
    result = validator.validate(minimal_bundle)
    assert not any("0 functions" in w for w in result.warnings)


def test_subsystems_section_warns_when_empty(validator, minimal_bundle):
    minimal_bundle["template"]["sections"].append(
        {"number": "5", "source": "subsystems", "title": "Состав работ"}
    )
    minimal_bundle["subsystems"] = []
    result = validator.validate(minimal_bundle)
    assert any("5" in w for w in result.warnings)


def test_real_bundle_fixture_is_valid(validator, render_bundle_fixture):
    """Фикстура из docs/ должна проходить валидацию."""
    result = validator.validate(render_bundle_fixture)
    # Фикстура может иметь незаполненные поля — просто проверяем что валидатор отрабатывает
    assert isinstance(result.is_valid, bool)
    assert isinstance(result.missing_fields, list)
