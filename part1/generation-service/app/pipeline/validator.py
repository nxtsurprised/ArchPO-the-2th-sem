from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    is_valid: bool
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BundleValidator:
    """
    Этап 1: валидация render-bundle перед генерацией.

    Проверяет:
    - Наличие обязательных полей в секциях типа 'manual'
    - Предупреждает о секциях 'functions' с нулевым количеством функций
    - Предупреждает о секциях 'subsystems' без подсистем
    """

    def validate(self, bundle: dict) -> ValidationResult:
        missing: list[str] = []
        warnings: list[str] = []

        template = bundle.get("template", {})
        data = bundle.get("data", {})
        sections_data: dict = data.get("sections", {})
        functions: list = bundle.get("functions", [])
        subsystems: list = bundle.get("subsystems", [])

        for section in template.get("sections", []):
            num = section.get("number", "?")
            source = section.get("source", "")

            if source == "manual":
                sec_data = sections_data.get(str(num), {})
                for f in section.get("fields", []):
                    if f.get("required") and not sec_data.get(f["key"]):
                        missing.append(f"section.{num}.{f['key']}")

            elif source == "functions":
                if not functions:
                    warnings.append(f"section.{num}: 0 functions")

            elif source == "subsystems":
                if not subsystems:
                    warnings.append(f"section.{num}: 0 subsystems")

        return ValidationResult(
            is_valid=len(missing) == 0,
            missing_fields=missing,
            warnings=warnings,
        )
