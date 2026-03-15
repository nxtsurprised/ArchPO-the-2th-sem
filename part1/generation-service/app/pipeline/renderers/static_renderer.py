from __future__ import annotations

from app.pipeline.renderers.manual_renderer import IRElement, IRHeading, IRParagraph


def render_static(section: dict) -> list[IRElement]:
    """Рендерит секцию типа 'static': заголовок + фиксированный текст."""
    num = section.get("number", "")
    title = section.get("title", "")
    static_content = section.get("static_content", "")

    elements: list[IRElement] = [IRHeading(text=f"{num} {title}".strip(), level=1)]

    if static_content:
        elements.append(IRParagraph(text=static_content))

    return elements


def render_subsystems(section: dict, subsystems: list[dict]) -> list[IRElement]:
    """Рендерит секцию типа 'subsystems': нумерованный список подсистем."""
    num = section.get("number", "")
    title = section.get("title", "")

    elements: list[IRElement] = [IRHeading(text=f"{num} {title}".strip(), level=1)]

    sorted_subs = sorted(subsystems, key=lambda s: s.get("order", 0))
    items = [
        f"{s.get('code', '')} — {s.get('name', '')}: {s.get('description', '')}".strip(" —:")
        for s in sorted_subs
    ]
    if items:
        from app.pipeline.renderers.manual_renderer import IRList
        elements.append(IRList(items=items, ordered=True))

    return elements
