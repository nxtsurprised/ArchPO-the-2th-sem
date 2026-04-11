# ГОСТ 2.105 — Карта стилей шаблона

Исходный файл: `generation-service/assets/gost-2105-template.dotx`
MinIO-ключ (production): `dotx/gost-2105-template.dotx`
Каталог использует этот ключ в `dotx_file_key` шаблонов ТЗ, ЧТЗ, ПМИ.

---

## Как это работает

`DocxBuilder` открывает `.dotx` как шаблон через `python-docx`:
```python
doc = Document(io.BytesIO(dotx_bytes))
paragraph.style = doc.styles[STYLE_MAP["heading_1"]]
```
Все форматирование (шрифт, отступы, интервалы) хранится в стилях `.dotx`. Python-код только присваивает стиль по имени.

При отсутствии `.dotx` — программный fallback в `docx_builder.py` (Times New Roman 14pt, ГОСТ-отступы вручную).

---

## Таблица стилей

### Заголовки разделов

| Ключ в STYLE_MAP | Имя стиля в .dotx | styleId | Параметры |
|------------------|-------------------|---------|-----------|
| `heading_1` | `heading 1` | `10` | 14pt, полужирный |
| `heading_2` | `heading 2` | `2` | полужирный |
| `heading_3` | `heading 3` | `3` | полужирный |
| `heading_4` | `heading 4` | `4` | — |
| `heading_unnumbered` | `ph_header_1_without_num` | `phheader1withoutnum` | ненумерованный |

### Основной текст

| Ключ | Имя стиля | styleId | Параметры |
|------|-----------|---------|-----------|
| `body_text` | `ph_normal` | `phnormal` | стандартный абзац |
| `body_base` | `ph_base` | `phbase` | 12pt базовый |

### Маркированные списки

| Ключ | Имя стиля | styleId | Уровень |
|------|-----------|---------|---------|
| `list_bullet` | `ph_list_itemized_1` | `phlistitemized1` | 1 |
| `list_bullet_2` | `ph_list_itemized_2` | `phlistitemized2` | 2 |
| `list_bullet_3` | `ph_list_itemized_3` | `phlistitemized3` | 3 |
| — | `ph_list_itemized_4` | `phlistitemized4` | 4 |

### Нумерованные списки

| Ключ | Имя стиля | styleId | Формат |
|------|-----------|---------|--------|
| `list_number` | `ph_list_ordered_1` | `phlistordered1` | 1) 2) 3) |
| `list_number_abc` | `ph_list_ordered_aбв` | `phlistordereda` | а) б) в) |

### Таблицы

| Ключ | Имя стиля | styleId | Назначение |
|------|-----------|---------|-----------|
| `table_cell` | `ph_table_cell` | `phtablecell` | ячейка, 10pt |
| `table_cell_center` | `ph_table_cellcenter` | `phtablecellcenter` | ячейка, выровнено по центру |
| `table_cell_left` | `ph_table_cellleft` | `phtablecellleft` | ячейка, выровнено влево |
| `table_head` | `ph_table_colcaption` | `phtablecolcaption` | заголовок колонки, полужирный |
| `table_title` | `ph_table_title` | `phtabletitle` | надпись таблицы |
| — | `Table Grid` | `a9` | стиль самой таблицы |

### Рисунки

| Ключ | Имя стиля | styleId | Назначение |
|------|-----------|---------|-----------|
| `figure_title` | `ph_figure_title` | `phfiguretitle` | подпись рисунка |
| `figure_graphic` | `ph_figure_graphic` | `phfiguregraphic` | контейнер изображения |

### Примечания и примеры

| Ключ | Имя стиля | styleId | Параметры |
|------|-----------|---------|-----------|
| `note` | `ph_normal_note` | `phnormalnote` | 10pt |
| `note_text` | `ph_normal_note_text` | `phnormalnotetext` | 10pt |
| `example` | `ph_example` | `phexample` | 10pt полужирный |
| `footnote` | `ph_footnote` | `phfootnote` | 9pt |

### Код / программный текст

| Ключ | Имя стиля | styleId | Шрифт |
|------|-----------|---------|-------|
| `code` | `Текст_программы` | `aa` | Courier New 12pt |

### Приложения

| Ключ | Имя стиля | styleId | Параметры |
|------|-----------|---------|-----------|
| `appendix_title_1` | `ph_addition_title_1` | `phadditiontitle1` | 14pt полужирный |
| `appendix_title_2` | `ph_addition_title_2` | `phadditiontitle2` | полужирный |
| `appendix_title_3` | `ph_addition_title_3` | `phadditiontitle3` | 11pt полужирный |

### Оглавление

| Ключ | Имя стиля | styleId |
|------|-----------|---------|
| `toc_1` | `toc 1` | `11` |
| `toc_2` | `toc 2` | `20` |
| `toc_3` | `toc 3` | `30` |

### Колонтитулы

| Ключ | Имя стиля | styleId | Параметры |
|------|-----------|---------|-----------|
| `header` | `ph_colontitulup` | `phcolontitulup` | 10pt |
| `footer` | `ph_colontituldown` | `phcolontituldown` | 10pt |

### Титульная страница

| Ключ | Имя стиля | styleId | Параметры |
|------|-----------|---------|-----------|
| `title_system_full` | `ph_titlepage_system_full` | `phtitlepagesystemfull` | 16pt полужирный |
| `title_system_short` | `ph_titlepage_system_short` | `phtitlepagesystemshort` | 16pt полужирный |
| `title_document` | `ph_titlepage_document` | `phtitlepagedocument` | 13pt полужирный |
| `title_customer` | `ph_titlepage_customer` | `phtitlepagecustomer` | 13pt полужирный |
| `title_code` | `ph_titlepage_code` | `phtitlepagecode` | 13pt полужирный |

---

## Inline (character) стили

Используются для оформления части текста внутри абзаца:

| styleId | Имя | Назначение |
|---------|-----|-----------|
| `phinline` | `ph_inline` | базовый inline |
| `phinlinebolditalic` | `ph_inline_bolditalic` | полужирный курсив |
| `phinlinecomputer` | `ph_inline_computer` | Courier New 12pt — код в тексте |
| `phinlinefirstterm` | `ph_inline_firstterm` | 12pt — первое упоминание термина |
| `phinlineunderline` | `ph_inline_underline` | подчёркнутый |
| `phinlineuppercase` | `ph_inline_uppercase` | ЗАГЛАВНЫЕ |
| `phinlinekeycap` | `ph_inline_keycap` | 12pt полужирный — клавиши |

---

## Размещение файла

### Production (MinIO)
```
bucket:  templates
key:     dotx/gost-2105-template.dotx
```
Generation Service скачивает при старте job-а и передаёт байты в `DocxBuilder(dotx_bytes=...)`.

### Development (локально)
```
generation-service/assets/gost-2105-template.dotx
```
Задать через переменную окружения:
```
DOTX_LOCAL_PATH=assets/gost-2105-template.dotx
```
Generation Service читает файл с диска если MinIO недоступен или `USE_LOCAL_DOTX=true`.

---

## Проверка стилей (отладка)

```python
# Убедиться, что все ключи STYLE_MAP присутствуют в шаблоне
import zipfile, xml.etree.ElementTree as ET
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with zipfile.ZipFile('generation-service/assets/gost-2105-template.dotx') as z:
    tree = ET.parse(z.open('word/styles.xml'))
    names = {
        el.find('w:name', NS).get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
        for el in tree.getroot().findall('w:style', NS)
        if el.find('w:name', NS) is not None
    }

from app.pipeline.formatters.gost_formatter import STYLE_MAP
missing = {k: v for k, v in STYLE_MAP.items() if v not in names}
print('Missing styles:', missing or 'none — all OK')
```
