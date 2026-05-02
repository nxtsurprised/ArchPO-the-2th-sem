from __future__ import annotations
from collections import defaultdict

from app.pipeline.renderers.manual_renderer import (
    IRElement, IRHeading, IRParagraph, IRList,
)


def render_functions(
    section: dict,
    functions: list[dict],
    subsystems: list[dict],
) -> list[IRElement]:
    """
    Этап 3 (ключевой): рендер функций, сгруппированных по подсистемам.

    Порядок подсистем определяется полем 'order'.
    Для каждой подсистемы:
      - H3: «4.2.N {subsystem.name}»
    Для каждой функции подсистемы:
      - H4: «{func.code} {func.name}»
      - Paragraph: func.description
      - NumberedList: func.requirements (если есть)
      - Paragraph: «Ограничения: {func.constraints}» (если есть)
    """
    num = section.get("number", "4.2")
    title = section.get("title", "")

    elements: list[IRElement] = [IRHeading(text=f"{num} {title}".strip(), level=1)]

    # Группируем функции по subsystem_id
    grouped: dict[str, list[dict]] = defaultdict(list)
    for func in functions:
        grouped[func.get("subsystem_id", "")].append(func)

    sorted_subsystems = sorted(subsystems, key=lambda s: s.get("order", 0))

    for idx, subsystem in enumerate(sorted_subsystems, start=1):
        sub_id = subsystem.get("id", "")
        sub_name = subsystem.get("name", "")

        elements.append(IRHeading(text=f"{num}.{idx} {sub_name}", level=3))

        for func in grouped.get(sub_id, []):
            code = func.get("code", "")
            name = func.get("name", "")
            description = func.get("description", "")
            requirements = func.get("requirements", [])
            constraints = func.get("constraints", "")

            elements.append(IRHeading(text=f"{code} {name}", level=4))

            if description:
                elements.append(IRParagraph(text=description))

            if requirements:
                req_items = [r.get("text", str(r)) if isinstance(r, dict) else str(r) for r in requirements]
                elements.append(IRList(items=req_items, ordered=True))

            if constraints:
                elements.append(IRParagraph(text=f"Ограничения: {constraints}"))

    return elements
