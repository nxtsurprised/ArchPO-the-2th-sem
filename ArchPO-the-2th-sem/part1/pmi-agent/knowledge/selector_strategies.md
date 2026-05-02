# Стратегии поиска CSS-селекторов

Руководство для агента Исполнителя по поиску элементов в DOM.
Применяй в порядке приоритета: от наиболее надежного к наименее.

---

## Приоритет 1: data-testid атрибуты (самый надежный)

```css
[data-testid="btn-login"]
[data-testid="input-email"]
[data-testid="row-{uuid}"]
[data-testid="error-email"]
```

Эти атрибуты добавлены специально для тестирования и не меняются при рефакторинге верстки.

**Когда использовать:** всегда, если элемент имеет data-testid.

---

## Приоритет 2: ARIA-роли и атрибуты

```css
[role="dialog"]
[role="alert"]
[role="combobox"]
[aria-label="Закрыть диалог"]
[aria-busy="true"]
button[aria-expanded="true"]
```

**Когда использовать:** интерактивные элементы без data-testid.

---

## Приоритет 3: Семантические HTML-атрибуты

```css
input[name="email"]
input[type="password"]
input[type="checkbox"][name="is_active"]
button[type="submit"]
form[action="/login"]
a[href="/dashboard"]
```

**Когда использовать:** стандартные элементы форм.

---

## Приоритет 4: Уникальный текст кнопки (через :has-text или text=)

В Playwright:
```python
page.get_by_role("button", name="Войти")
page.get_by_text("Неверный email или пароль")
page.get_by_label("Email")
page.get_by_placeholder("Введите email")
```

**Когда использовать:** когда нет data-testid и имени/роли.

---

## Приоритет 5: Комбинированные CSS-селекторы

```css
.card:nth-child(1) button.btn-primary
table tbody tr:first-child td:last-child button
.modal-body .form-group:has(label:text("Email")) input
```

**Когда использовать:** как последний вариант, хрупкие — могут сломаться при рефакторинге.

---

## Антипаттерны (не использовать)

❌ `div > div > div > button` — слишком хрупко
❌ `.css-abc123` — автогенерированные CSS-классы меняются
❌ `//button[@class="btn btn-primary btn-lg"]` — XPath, избегай в Playwright

---

## Стратегия поиска при отсутствии селектора

Если элемент не найден по ожидаемому селектору:

1. Сделать скриншот страницы
2. Запросить DOM-фрагмент (`page.content()` или `page.locator("body").inner_html()`)
3. Поиск по ключевым словам в тексте (get_by_text)
4. Поиск по ближайшему известному родителю

---

## Ожидание элементов (важно!)

```python
# Ждать появления элемента (макс. 5 секунд)
await page.wait_for_selector("[data-testid='btn-save']", timeout=5000)

# Ждать исчезновения лоадера
await page.wait_for_selector("[data-testid='loading']", state="hidden", timeout=10000)

# Ждать навигации
await page.wait_for_load_state("networkidle")

# Ждать конкретного URL
await page.wait_for_url("**/dashboard", timeout=5000)
```

---

## Перехват HTTP-запросов

```python
# Перехватить ответ API
async with page.expect_response("**/api/v1/auth/login") as response_info:
    await page.click("[data-testid='btn-login']")
response = await response_info.value
json_body = await response.json()
```

Используй для проверки кодов ответа и тела без UI-элементов.

---

## Специфика приложения ГОСТ 34

| Элемент | Ожидаемый селектор |
|---|---|
| Кнопка входа | `[data-testid="btn-login"]` или `button[type="submit"]` |
| Поле email | `input[name="email"]` |
| Поле пароль | `input[name="password"]` |
| Кнопка «Создать» | `[data-testid="btn-create"]` |
| Кнопка «Сгенерировать» | `[data-testid="btn-generate"]` |
| Кнопка «Отправить на согласование» | `[data-testid="btn-submit-approval"]` |
| Статус документа | `[data-testid="document-status"]` |
| Бейдж роли пользователя | `[data-testid="user-role-badge"]` |
| Сообщение об ошибке | `[role="alert"]` или `[data-testid="error-message"]` |
