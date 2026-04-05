# История результатов испытаний (few-shot примеры)

Эта база знаний содержит примеры успешно сгенерированных тест-планов и разделов ПМИ.
Используй как эталонные примеры при создании новых документов.

---

## Пример 1: Тест-план для F-AUTH-02 (Аутентификация)

```json
{
  "function_id": "F-AUTH-02",
  "function_name": "Аутентификация (вход) в систему",
  "objective": "Проверить корректность аутентификации пользователя по логину и паролю с выдачей JWT",
  "preconditions": [
    "Пользователь с email test@example.com и ролью pm_contractor зарегистрирован в системе",
    "Система доступна по адресу http://localhost:8080",
    "База данных инициализирована seed-данными"
  ],
  "steps": [
    {
      "step_number": 1,
      "action": "navigate",
      "description": "Перейти на страницу входа",
      "target": "/login",
      "expected_result": "Отображается форма входа с полями email и пароль"
    },
    {
      "step_number": 2,
      "action": "fill",
      "description": "Ввести email пользователя",
      "target": "input[name='email']",
      "input_data": "test@example.com",
      "expected_result": "Поле заполнено"
    },
    {
      "step_number": 3,
      "action": "fill",
      "description": "Ввести пароль",
      "target": "input[name='password']",
      "input_data": "Test1234!",
      "expected_result": "Поле заполнено"
    },
    {
      "step_number": 4,
      "action": "click",
      "description": "Нажать кнопку Войти",
      "target": "button[type='submit']",
      "expected_result": "Инициирован запрос POST /api/v1/auth/login"
    },
    {
      "step_number": 5,
      "action": "assert",
      "description": "Проверить перенаправление на дашборд",
      "target": "url",
      "expected_result": "URL страницы содержит /dashboard"
    },
    {
      "step_number": 6,
      "action": "assert",
      "description": "Проверить наличие JWT в хранилище",
      "target": "localStorage.token",
      "expected_result": "Токен присутствует и не пустой"
    }
  ],
  "postconditions": ["Пользователь авторизован в системе"],
  "gost_method": "Проверка"
}
```

---

## Пример 2: Раздел ПМИ для F-AUTH-02 (успешный результат)

```json
{
  "function_id": "F-AUTH-02",
  "function_name": "Аутентификация (вход) в систему",
  "test_objective": "Проверить корректность аутентификации по логину и паролю",
  "method": "Проверка",
  "gost_ref": "ГОСТ 34.603-92, п. 5.1",
  "steps_total": 6,
  "steps_passed": 6,
  "steps_failed": 0,
  "verdict": "соответствует",
  "observations": "В ходе испытания выполнен вход в систему с корректными учетными данными. Пользователь с ролью pm_contractor успешно аутентифицирован. Наблюдаемый результат: после нажатия кнопки «Войти» выполнен POST-запрос на /api/v1/auth/login, получен HTTP 200 с JWT-токеном, произошло перенаправление на /dashboard. Имя пользователя отображается в заголовке приложения. JWT-токен присутствует в localStorage.",
  "defects": [],
  "recommendation": "Функция допускается к опытной эксплуатации."
}
```

---

## Пример 3: Тест-план для F-GEN-04 (НМЦК)

```json
{
  "function_id": "F-GEN-04",
  "function_name": "Генерация НМЦК (.xlsx с формулами)",
  "objective": "Проверить генерацию файла расчета НМЦК с активными Excel-формулами",
  "preconditions": [
    "Справочник функций заполнен (минимум 3 функции с трудоемкостью)",
    "Ставки занесены в систему",
    "Документ НМЦК создан в проекте"
  ],
  "steps": [
    {
      "step_number": 1,
      "action": "navigate",
      "description": "Перейти к документу НМЦК",
      "target": "/documents/{nmck_id}",
      "expected_result": "Открыта карточка документа НМЦК"
    },
    {
      "step_number": 2,
      "action": "click",
      "description": "Нажать кнопку Сгенерировать",
      "target": "[data-testid='btn-generate']",
      "expected_result": "Началась генерация, отображается индикатор прогресса"
    },
    {
      "step_number": 3,
      "action": "assert",
      "description": "Дождаться завершения генерации",
      "target": "[data-testid='btn-download']",
      "expected_result": "Появилась кнопка Скачать"
    },
    {
      "step_number": 4,
      "action": "api_call",
      "description": "Скачать файл через API",
      "target": "GET /api/v1/documents/{nmck_id}/download",
      "expected_result": "HTTP 200, Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }
  ],
  "postconditions": ["Файл .xlsx сохранен в MinIO"],
  "gost_method": "Проверка"
}
```

---

## Пример 4: Раздел ПМИ с дефектом (частичное соответствие)

```json
{
  "function_id": "F-WF-01",
  "function_name": "Создание запроса на согласование",
  "verdict": "соответствует частично",
  "observations": "Функция отправки документа на согласование работает корректно: POST-запрос возвращает HTTP 201, документ блокируется. Однако при отправке не отображается уведомление об успехе (toast-сообщение) — пользователь не получает визуального подтверждения.",
  "defects": [
    "Отсутствует уведомление об успешной отправке на согласование (UI-замечание)"
  ],
  "recommendation": "Устранить замечание по UI до приемочных испытаний."
}
```
