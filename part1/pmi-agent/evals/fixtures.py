"""
Тест-кейсы с известными входными данными и ожидаемыми свойствами выходов.

Каждый кейс описывает функцию системы и минимальные требования к тест-плану/секции.
Используются как в unit-evals (оценка без LLM), так и в интеграционных evals (с реальным LLM).
"""

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    id: str
    function_id: str
    function_name: str
    function_description: str
    acceptance_criteria: list[str]

    # Минимальные ожидания к выходу планировщика
    min_steps: int = 2
    expected_actions: list[str] = field(default_factory=lambda: ["navigate", "assert"])
    keywords_in_steps: list[str] = field(default_factory=list)

    # Ожидаемый вердикт при всех passed / всех failed
    verdict_all_passed: str = "соответствует"
    verdict_all_failed: str = "не соответствует"

    # Описание — для читаемости отчёта
    description: str = ""


EVAL_CASES: list[EvalCase] = [
    EvalCase(
        id="auth-login",
        function_id="F-AUTH-01",
        function_name="Аутентификация пользователя",
        function_description=(
            "Пользователь вводит логин и пароль на странице /login. "
            "При корректных данных система выдаёт JWT и перенаправляет на главную. "
            "При трёх неверных попытках — блокировка на 30 минут."
        ),
        acceptance_criteria=[
            "Успешный вход перенаправляет на /dashboard",
            "Неверный пароль показывает сообщение об ошибке",
            "После 3 ошибок появляется сообщение о блокировке",
            "Форма имеет поля email и password",
        ],
        min_steps=4,
        expected_actions=["navigate", "fill", "click", "assert"],
        keywords_in_steps=["login", "пароль", "email", "блокировк"],
        description="Стандартная функция аутентификации с блокировкой",
    ),

    EvalCase(
        id="document-create",
        function_id="F-CATALOG-03",
        function_name="Создание документа в каталоге",
        function_description=(
            "Авторизованный пользователь с ролью PM или analyst может создать документ "
            "через кнопку «Добавить» на странице проекта. "
            "Документ требует указания названия и типа (ТЗ/ЧТЗ/ПМИ/НМЦК)."
        ),
        acceptance_criteria=[
            "Кнопка «Добавить документ» доступна только для PM/analyst",
            "Без выбора типа документа форма не отправляется",
            "Созданный документ появляется в списке со статусом 'черновик'",
        ],
        min_steps=3,
        expected_actions=["navigate", "click", "assert"],
        keywords_in_steps=["документ", "тип", "добавить"],
        description="Создание документа с валидацией обязательных полей",
    ),

    EvalCase(
        id="approval-round",
        function_id="F-WORKFLOW-02",
        function_name="Согласование документа",
        function_description=(
            "PM отправляет документ на согласование. Создаётся раунд согласования. "
            "Представители заказчика и подрядчика принимают решение (утвердить/отклонить/на доработку). "
            "Раунд завершается только после решения обоих РП."
        ),
        acceptance_criteria=[
            "Кнопка 'Отправить на согласование' переводит документ в статус 'на согласовании'",
            "Пользователь без роли PM не видит кнопку",
            "После решения 'Утвердить' обоими РП статус меняется на 'утверждён'",
            "После 'На доработку' документ возвращается в статус 'на доработке'",
        ],
        min_steps=5,
        expected_actions=["navigate", "click", "assert"],
        keywords_in_steps=["согласован", "статус", "утверд"],
        description="Многораундовый workflow согласования",
    ),

    EvalCase(
        id="generate-docx",
        function_id="F-GEN-01",
        function_name="Генерация DOCX-документа",
        function_description=(
            "Пользователь нажимает 'Сгенерировать файл' на странице документа. "
            "Система запускает generation-service, который рендерит .docx по шаблону ГОСТ 2.105. "
            "После завершения появляется ссылка для скачивания."
        ),
        acceptance_criteria=[
            "Кнопка 'Сгенерировать файл' запускает процесс генерации",
            "Во время генерации отображается индикатор загрузки",
            "После завершения появляется ссылка на скачивание",
            "Скачанный файл имеет расширение .docx",
        ],
        min_steps=4,
        expected_actions=["navigate", "click", "assert"],
        keywords_in_steps=["генерац", "скачать", "docx", "файл"],
        description="Генерация и скачивание DOCX",
    ),

    EvalCase(
        id="role-access-control",
        function_id="F-AUTH-05",
        function_name="Ролевая модель доступа",
        function_description=(
            "Система разграничивает доступ по ролям: superadmin, org_admin, pm, analyst, "
            "customer_pm, contractor_pm, viewer. "
            "Пользователь видит только то, к чему у него есть права."
        ),
        acceptance_criteria=[
            "Viewer не видит кнопки редактирования",
            "Пользователь без назначенной роли в проекте не может открыть проект",
            "Admin видит все проекты организации",
        ],
        min_steps=4,
        expected_actions=["navigate", "assert"],
        keywords_in_steps=["роль", "доступ", "viewer", "admin"],
        description="Проверка ролевого разграничения доступа",
    ),
]


# Сгенерированные тест-планы с заведомо известными свойствами — для evals writer-а
SAMPLE_TEST_PLANS = {
    "good_plan": {
        "function_id": "F-AUTH-01",
        "function_name": "Аутентификация пользователя",
        "objective": "Проверить корректность аутентификации по ГОСТ 34.603",
        "preconditions": ["Система запущена", "Тестовый пользователь создан"],
        "gost_method": "Проверка",
        "steps": [
            {
                "step_number": 1, "action": "navigate",
                "description": "Открыть страницу входа",
                "target": "/login", "input_data": None,
                "expected_result": "Отображается форма с полями email и password",
                "gost_ref": "п. 5.1 ГОСТ 34.603-92",
            },
            {
                "step_number": 2, "action": "fill",
                "description": "Ввести корректные учётные данные",
                "target": "input[name=email]", "input_data": "user@test.ru",
                "expected_result": "Поле заполнено",
                "gost_ref": "п. 5.2 ГОСТ 34.603-92",
            },
            {
                "step_number": 3, "action": "click",
                "description": "Нажать кнопку 'Войти'",
                "target": "button[type=submit]", "input_data": None,
                "expected_result": "Выполнен переход на /dashboard",
                "gost_ref": "п. 5.3 ГОСТ 34.603-92",
            },
            {
                "step_number": 4, "action": "assert",
                "description": "Проверить перенаправление на dashboard",
                "target": "url", "input_data": None,
                "expected_result": "URL содержит /dashboard",
                "gost_ref": "п. 5.3 ГОСТ 34.603-92",
            },
        ],
        "postconditions": ["Пользователь авторизован", "JWT-токен выдан"],
    },

    "minimal_plan": {
        # Минимально допустимый план — только обязательные поля
        "function_id": "F-TEST-99",
        "function_name": "Тест",
        "objective": "Проверить",
        "preconditions": [],
        "gost_method": "Проверка",
        "steps": [
            {
                "step_number": 1, "action": "navigate",
                "description": "Открыть приложение",
                "target": "/", "input_data": None,
                "expected_result": "Страница загружена",
                "gost_ref": None,
            },
        ],
        "postconditions": [],
    },

    "no_gost_plan": {
        # План без ссылок на ГОСТ — должен штрафоваться в метрике gost_coverage
        "function_id": "F-TEST-88",
        "function_name": "Без ГОСТ",
        "objective": "Что-то проверить",
        "preconditions": [],
        "gost_method": "Проверка",
        "steps": [
            {"step_number": i, "action": "assert",
             "description": f"Шаг {i}", "target": "url", "input_data": None,
             "expected_result": "Ок", "gost_ref": None}
            for i in range(1, 4)
        ],
        "postconditions": [],
    },
}


SAMPLE_STEP_RESULTS = {
    "all_passed": [
        {"step_number": i, "status": "passed", "actual_result": "Ок", "error_message": None}
        for i in range(1, 5)
    ],
    "all_failed": [
        {"step_number": i, "status": "failed", "actual_result": "Ошибка", "error_message": "Element not found"}
        for i in range(1, 5)
    ],
    "partial": [
        {"step_number": 1, "status": "passed", "actual_result": "Ок", "error_message": None},
        {"step_number": 2, "status": "passed", "actual_result": "Ок", "error_message": None},
        {"step_number": 3, "status": "failed", "actual_result": "Ошибка", "error_message": "Timeout"},
        {"step_number": 4, "status": "failed", "actual_result": "Ошибка", "error_message": "Timeout"},
    ],
}
