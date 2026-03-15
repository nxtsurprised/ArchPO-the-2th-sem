from __future__ import annotations

# ГОСТ 2.105-2019 — маппинг семантических имён на стили .dotx
STYLE_MAP: dict[str, str] = {
    "heading_1":   "Заголовок 1",
    "heading_2":   "Заголовок 2",
    "heading_3":   "Заголовок 3",
    "heading_4":   "Заголовок 4",
    "body_text":   "Основной текст",
    "list_bullet": "Маркированный",
    "list_number": "Нумерованный",
    "table_head":  "Шапка таблицы",
    "table_cell":  "Ячейка таблицы",
}

# Параметры страницы ГОСТ 2.105-2019 в единицах DXA (1/1440 дюйма)
PAGE_SETTINGS = {
    "width":   11906,   # A4 210 мм
    "height":  16838,   # A4 297 мм
    "left":    1701,    # поле 30 мм
    "right":   850,     # поле 15 мм
    "top":     1134,    # поле 20 мм
    "bottom":  1134,    # поле 20 мм
}

# Параметры шрифта и интервалов
FONT_SETTINGS = {
    "name":         "Times New Roman",
    "size_pt":      14,
    "size_half_pt": 28,       # python-docx использует half-points
    "line_spacing": 360,      # 1,5 строки в единицах twip
    "first_line":   709,      # абзацный отступ 1,25 см
}


def heading_style_name(level: int) -> str:
    """Возвращает имя стиля для заголовка заданного уровня (1–4)."""
    key = f"heading_{level}" if level <= 4 else "heading_4"
    return STYLE_MAP.get(key, f"Заголовок {level}")


def body_style_name() -> str:
    return STYLE_MAP["body_text"]


def list_style_name(ordered: bool) -> str:
    return STYLE_MAP["list_number"] if ordered else STYLE_MAP["list_bullet"]
