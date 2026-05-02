from __future__ import annotations

# ГОСТ 2.105-2019 — маппинг семантических имён на стили .dotx
#
# Значения — точные имена стилей из word/styles.xml шаблона
# generation-service/assets/gost-2105-template.dotx.
# Именно их видит python-docx при doc.styles[name].
STYLE_MAP: dict[str, str] = {
    # ── Заголовки (русские имена, как в .dotx) ──────────────────────────────
    "heading_1":                "Заголовок 1",
    "heading_2":                "Заголовок 2",
    "heading_3":                "Заголовок 3",
    "heading_4":                "Заголовок 4",
    "heading_5":                "Заголовок 5",
    "heading_6":                "Заголовок 6",

    # ── Основной текст ──────────────────────────────────────────────────────
    "body_text":                "ph_normal",

    # ── Оглавление ──────────────────────────────────────────────────────────
    "toc":                      "ph_content",

    # ── Вводная фраза перед списком ─────────────────────────────────────────
    "list_intro":               "ph_list_itemized_title",   # перед маркированным
    "list_ordered_intro":       "ph_list_ordered_title",    # перед нумерованным

    # ── Маркированные списки ────────────────────────────────────────────────
    "list_bullet":              "ph_list_itemized_1",
    "list_bullet_2":            "ph_list_itemized_2",
    "list_bullet_3":            "ph_list_itemized_3",
    "list_bullet_4":            "ph_list_itemized_4",

    # ── Нумерованные / буквенные списки ─────────────────────────────────────
    "list_number":              "ph_list_ordered_1_up",
    "list_number_abc":          "ph_list_ordered_абв",

    # ── Таблицы ─────────────────────────────────────────────────────────────
    "table_title":              "ph_table_title",
    "table_head":               "ph_table_colcaption",
    "table_cell":               "ph_table_cellleft",
    "table_list_bullet":        "ph_table_itemizedlist_1",
    "table_list_bullet_2":      "ph_table_itemizedlist_2",
    "table_list_number":        "ph_table_orderedlist_1",
    "table_list_abc":           "ph_table_orderedlist_абв",

    # ── Рисунки ─────────────────────────────────────────────────────────────
    "figure":                   "ph_figure",
    "figure_title":             "ph_figure_title",
    "figure_title_note":        "ph_figure_title_note",
    "figure_title_example":     "ph_figure_title_example",

    # ── Примечания ──────────────────────────────────────────────────────────
    "note":                     "ph_normal_note",           # слово «Примечание»
    "note_text":                "ph_normal_note_text",
    "note_list_bullet":         "ph_normal_note_itemized_1",
    "note_list_bullet_2":       "ph_normal_note_itemized_2",
    "note_list_number":         "ph_normal_note_ordered_1",

    # ── Примеры ─────────────────────────────────────────────────────────────
    "example":                  "ph_normal_example",        # слово «Пример»
    "example_text":             "ph_normal_example_text",
    "example_list_bullet":      "ph_normal_example_itemized_1",
    "example_list_bullet_2":    "ph_normal_example_itemized_2",
    "example_list_number":      "ph_normal_example_ordered_1",

    # ── Сноска ──────────────────────────────────────────────────────────────
    "footnote":                 "ph_footnote",

    # ── Приложения ──────────────────────────────────────────────────────────
    "appendix_title_1":         "ph_addition_title_1",      # Приложение А
    "appendix_title_2":         "ph_addition_title_2",      # А.1
    "appendix_title_3":         "ph_addition_title_3",      # А.1.1

    # ── Программный код ─────────────────────────────────────────────────────
    "code":                     "Текст_программы",

    # ── Титульная страница ──────────────────────────────────────────────────
    "title_system_full":        "ph_titlepage_system_full",
    "title_system_short":       "ph_titlepage_system_short",
    "title_document":           "ph_titlepage_document",
    "title_other":              "ph_titlepage_other",       # фраза с кол-вом страниц
    "title_docpart":            "ph_titlepage_docpart",     # колонтитулы титула
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

# Параметры шрифта и интервалов (используются только в programmatic fallback)
FONT_SETTINGS = {
    "name":         "Times New Roman",
    "size_pt":      14,
    "size_half_pt": 28,
    "line_spacing": 360,    # 1,5 строки в twip
    "first_line":   709,    # абзацный отступ 1,25 см
}


def heading_style_name(level: int) -> str:
    """Возвращает имя стиля для заголовка заданного уровня (1–6)."""
    key = f"heading_{min(level, 6)}"
    return STYLE_MAP.get(key, f"Заголовок {level}")


def body_style_name() -> str:
    return STYLE_MAP["body_text"]


def list_style_name(ordered: bool) -> str:
    return STYLE_MAP["list_number"] if ordered else STYLE_MAP["list_bullet"]
