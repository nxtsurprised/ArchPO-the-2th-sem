# Паттерны пользовательского интерфейса системы ГОСТ 34

Описание типовых UI-элементов и ожидаемого поведения фронтенда (React 18 + Vite).
Используй для написания шагов тест-плана с правильными ожиданиями.

---

## Маршрутизация (React Router)

| Маршрут | Страница | Права |
|---|---|---|
| `/login` | Вход в систему | Нет |
| `/` или `/dashboard` | Дашборд | Любой авторизованный |
| `/projects` | Список проектов | pm, admin |
| `/projects/:id` | Детали проекта | Участник проекта |
| `/catalog/templates` | Шаблоны документов | analyst+ |
| `/catalog/functions` | Справочник функций | analyst+ |
| `/documents/:id` | Документ | Участник проекта |
| `/documents/:id/generate` | Генерация | pm, analyst |
| `/approvals` | Согласования | rp, pm |
| `/approvals/:id` | Детали согласования | rp, pm |
| `/audit` | Журнал аудита | admin, superadmin |
| `/admin/users` | Управление пользователями | admin |

---

## Типовые компоненты

### Кнопки
- Основное действие: `[data-testid="btn-primary"]` или `button[type="submit"]`
- Отмена: `[data-testid="btn-cancel"]` или `button[type="button"]`
- Удаление: `[data-testid="btn-delete"]` — обычно красная, требует подтверждения

### Формы
- Поле ввода: `input[name="<fieldName>"]` или `[data-testid="input-<fieldName>"]`
- Выпадающий список: `select[name="<fieldName>"]` или кастомный Select с `[role="combobox"]`
- Чекбокс: `input[type="checkbox"][name="<fieldName>"]`
- Textarea: `textarea[name="<fieldName>"]`

### Уведомления / Toast
- Успех: элемент с классом `.toast-success` или `[role="alert"][data-type="success"]`
- Ошибка: `.toast-error` или `[role="alert"][data-type="error"]`
- Текст ошибки валидации под полем: `.field-error` или `[data-testid="error-<fieldName>"]`

### Таблицы со списками
- Строка таблицы: `tr[data-id="<uuid>"]` или `[data-testid="row-<uuid>"]`
- Кнопка «Редактировать» в строке: `[data-testid="edit-<uuid>"]`
- Кнопка «Удалить» в строке: `[data-testid="delete-<uuid>"]`
- Пагинация: `[data-testid="pagination"]`

### Диалоги подтверждения
- Модальное окно: `[role="dialog"]`
- Кнопка подтверждения: `[data-testid="confirm-delete"]` или `[data-testid="btn-confirm"]`

---

## Состояния загрузки

- Спиннер/лоадер: `[data-testid="loading"]` или `[aria-busy="true"]`
- Skeleton: `.skeleton` или `[data-testid="skeleton"]`
- Кнопка в состоянии ожидания: `button[disabled]` или `button[aria-busy="true"]`

Ожидай исчезновения лоадера перед проверкой результата.

---

## Аутентификация в UI

- Поле email: `input[name="email"]` или `input[type="email"]`
- Поле пароль: `input[name="password"]` или `input[type="password"]`
- Кнопка входа: `button[type="submit"]` или `[data-testid="btn-login"]`
- Ссылка «Забыл пароль»: `a[href="/reset-password"]`

После успешного входа:
- Происходит редирект на `/dashboard`
- В localStorage/sessionStorage появляется ключ `token`
- В заголовке приложения отображается имя пользователя

---

## Типичные сообщения об ошибках

| Ситуация | Ожидаемое сообщение |
|---|---|
| Неверный пароль | «Неверный email или пароль» |
| Аккаунт заблокирован | «Аккаунт заблокирован» |
| Нет прав | «Недостаточно прав для выполнения действия» или 403 |
| Объект не найден | «Не найдено» или 404 |
| Конфликт (дубль) | «Запись с таким именем уже существует» или 409 |
| Ошибка сервера | «Внутренняя ошибка сервера. Попробуйте позже» или 500 |

---

## Паттерн «Блокировка документа»

Когда документ отправлен на согласование:
- Кнопка «Редактировать» исчезает или становится `disabled`
- Статус документа меняется на «На согласовании» (badge/chip)
- Попытка PUT/PATCH через API возвращает 409 с `{"error": {"code": "DOCUMENT_LOCKED"}}`

---

## Паттерн загрузки файлов

- Кнопка скачивания: `a[download]` или `[data-testid="btn-download"]`
- После нажатия браузер запрашивает URL вида `/api/v1/documents/:id/download`
- Content-Type ответа: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

---

## Советы по написанию шагов

1. Всегда указывай `await page.waitForLoadState("networkidle")` после навигации
2. Для форм — сначала `fill`, потом `click` на Submit
3. Для выпадающих списков — `selectOption` или последовательность click + click на нужный вариант
4. Перед assert на видимость элемента — `waitForSelector` с таймаутом 5 секунд
