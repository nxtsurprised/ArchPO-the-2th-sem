from __future__ import annotations
from dataclasses import dataclass


@dataclass
class IRHeading:
    text: str
    level: int  # 1, 2, 3, 4


@dataclass
class IRParagraph:
    text: str
    style: str | None = None  # ключ из STYLE_MAP; None → body_text


@dataclass
class IRList:
    items: list[str]
    ordered: bool = False
    style: str | None = None  # ключ из STYLE_MAP; None → list_bullet / list_number


@dataclass
class IRTable:
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


# Союз всех IR-элементов
IRElement = IRHeading | IRParagraph | IRList | IRTable


def render_manual(section: dict, data: dict) -> list[IRElement]:
    """
    Рендерит секцию типа 'manual': берёт значения полей из data и формирует IR.
    """
    num = section.get("number", "")
    title = section.get("title", "")
    sec_data = data.get("sections", {}).get(str(num), {})

    elements: list[IRElement] = [IRHeading(text=f"{num} {title}".strip(), level=1)]

    for field_def in section.get("fields", []):
        key = field_def["key"]
        label = field_def.get("label", key)
        value = sec_data.get(key)

        if not value:
            continue

        ftype = field_def.get("type", "text")

        if ftype == "list":
            # Значение может быть строкой через перенос строки или уже списком
            if isinstance(value, list):
                items = [str(i) for i in value]
            else:
                items = [line.strip() for line in str(value).splitlines() if line.strip()]
            elements.append(IRParagraph(text=f"{label}:", style="list_intro"))
            elements.append(IRList(items=items, ordered=False))
        else:
            elements.append(IRParagraph(text=f"{label}: {value}"))

    return elements
