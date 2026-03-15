from __future__ import annotations

from app.pipeline.renderers.manual_renderer import IRElement, render_manual
from app.pipeline.renderers.function_renderer import render_functions
from app.pipeline.renderers.static_renderer import render_static, render_subsystems


def render_section(
    section: dict,
    bundle: dict,
) -> list[IRElement]:
    """
    Диспетчер: выбирает нужный рендерер по полю section.source.

    Поддерживаемые типы:
    - manual     → render_manual
    - functions  → render_functions
    - subsystems → render_subsystems
    - static     → render_static
    """
    source = section.get("source", "static")
    data = bundle.get("data", {})
    functions = bundle.get("functions", [])
    subsystems = bundle.get("subsystems", [])

    match source:
        case "manual":
            return render_manual(section, data)
        case "functions":
            return render_functions(section, functions, subsystems)
        case "subsystems":
            return render_subsystems(section, subsystems)
        case "static" | _:
            return render_static(section)
