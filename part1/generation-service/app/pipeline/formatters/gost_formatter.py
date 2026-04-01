from __future__ import annotations

# ГОСТ 2.105-2019 — маппинг семантических имён на стили .dotx
#
# Имена соответствуют файлу ГОСТ_2.105_шаблон_Times_NR.dotx
# (generation-service/assets/gost-2105-template.dotx).
# Значения — атрибут w:name из word/styles.xml, именно так их видит python-docx.
# При отсутствии .dotx DocxBuilder падает на программный fallback (см. docx_builder.py).
STYLE_MAP: dict[str, str] = {
    # ── Заголовки разделов ──────────────────────────────────────────────────
    "heading_1":           "heading 1",             # styleId=10, 14pt bold, нумерованный раздел
    "heading_2":           "heading 2",             # styleId=2,  bold, нумерованный подраздел
    "heading_3":           "heading 3",             # styleId=3,  bold, нумерованный пункт
    "heading_4":           "heading 4",             # styleId=4
    "heading_unnumbered":  "ph_header_1_without_num",  # ненумерованный заголовок (приложения, рефераты)

    # ── Основной текст ──────────────────────────────────────────────────────
    "body_text":           "ph_normal",             # styleId=phnormal, стандартный абзац
    "body_base":           "ph_base",               # styleId=phbase, 12pt базовый

    # ── Маркированные списки ────────────────────────────────────────────────
    "list_bullet":         "ph_list_itemized_1",    # styleId=phlistitemized1, уровень 1
    "list_bullet_2":       "ph_list_itemized_2",    # styleId=phlistitemized2, уровень 2
    "list_bullet_3":       "ph_list_itemized_3",    # styleId=phlistitemized3, уровень 3

    # ── Нумерованные списки ─────────────────────────────────────────────────
    "list_number":         "ph_list_ordered_1",     # styleId=phlistordered1, 1) 2) 3)
    "list_number_abc":     "ph_list_ordered_aбв",   # styleId=phlistordereda, а) б) в)

    # ── Таблицы ─────────────────────────────────────────────────────────────
    "table_cell":          "ph_table_cell",         # styleId=phtablecell, 10pt
    "table_cell_center":   "ph_table_cellcenter",   # styleId=phtablecellcenter
    "table_cell_left":     "ph_table_cellleft",     # styleId=phtablecellleft
    "table_head":          "ph_table_colcaption",   # styleId=phtablecolcaption, жирный заголовок колонки
    "table_title":         "ph_table_title",        # styleId=phtabletitle, подпись таблицы

    # ── Рисунки ─────────────────────────────────────────────────────────────
    "figure_title":        "ph_figure_title",       # styleId=phfiguretitle, подпись рисунка
    "figure_graphic":      "ph_figure_graphic",     # styleId=phfiguregraphic, контейнер рисунка

    # ── Примечания и примеры ────────────────────────────────────────────────
    "note":                "ph_normal_note",        # styleId=phnormalnote, 10pt
    "note_text":           "ph_normal_note_text",   # styleId=phnormalnotetext, 10pt
    "example":             "ph_example",            # styleId=phexample, 10pt bold
    "footnote":            "ph_footnote",           # styleId=phfootnote, 9pt

    # ── Код / программный текст ─────────────────────────────────────────────
    "code":                "Текст_программы",       # styleId=aa, Courier New 12pt

    # ── Приложения ──────────────────────────────────────────────────────────
    "appendix_title_1":    "ph_addition_title_1",   # styleId=phadditiontitle1, 14pt bold
    "appendix_title_2":    "ph_addition_title_2",   # styleId=phadditiontitle2, bold
    "appendix_title_3":    "ph_addition_title_3",   # styleId=phadditiontitle3, 11pt bold

    # ── Оглавление ──────────────────────────────────────────────────────────
    "toc_1":               "toc 1",                 # styleId=11, bold
    "toc_2":               "toc 2",                 # styleId=20
    "toc_3":               "toc 3",                 # styleId=30

    # ── Колонтитулы ─────────────────────────────────────────────────────────
    "header":              "ph_colontitulup",        # styleId=phcolontitulup, 10pt
    "footer":              "ph_colontituldown",      # styleId=phcolontituldown, 10pt

    # ── Титульная страница ──────────────────────────────────────────────────
    "title_system_full":   "ph_titlepage_system_full",   # styleId=phtitlepagesystemfull, 16pt bold
    "title_system_short":  "ph_titlepage_system_short",  # styleId=phtitlepagesystemshort, 16pt bold
    "title_document":      "ph_titlepage_document",      # styleId=phtitlepagedocument, 13pt bold
    "title_customer":      "ph_titlepage_customer",      # styleId=phtitlepagecustomer, 13pt bold
    "title_code":          "ph_titlepage_code",          # styleId=phtitlepagecode, 13pt bold
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
