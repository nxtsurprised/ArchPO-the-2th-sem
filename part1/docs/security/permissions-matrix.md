# Матрица прав доступа

## Роли

| Код | Название | Scope |
|-----|----------|-------|
| pm | Руководитель проекта | В рамках проекта, обе стороны |
| admin | Администратор проекта | В рамках проекта, своя сторона |
| analyst | Аналитик | В рамках проекта, обе стороны |
| superadmin | Системный администратор | Надпроектный (флаг is_superadmin) |

Роли pm, admin, analyst — проектные (привязаны через user_project_roles). Superadmin — глобальный (флаг в users).

Сторона (customer/contractor) определяется через project.customer_org_id / contractor_org_id.

## Обозначения

- ✓ — разрешено
- ✗ — запрещено
- ~ — частично (с ограничениями, описаны в примечаниях)

## Auth Service (8 permissions)

| Permission | Описание | pm_cust | admin_cust | analyst_cust | pm_cont | admin_cont | analyst_cont | superadmin |
|-----------|----------|---------|-----------|-------------|---------|-----------|-------------|-----------|
| user.create | Создание аккаунта (своя сторона) | ✗ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| user.deactivate | Деактивация (своя сторона) | ✗ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| user.assign_role | Назначение ролей | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| user.reset_password | Сброс пароля (своя сторона) | ✗ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| user.force_logout | Принудительный выход | ✗ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| audit.view | Просмотр журнала аудита | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| audit.view_unified | Агрегированный аудит всех сервисов | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| user.view_full_pdn | Просмотр полных ПДн (без маскирования) | ✗ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |

## Catalog Service — Подсистемы (5 permissions)

| Permission | Описание | pm_cust | admin_cust | analyst_cust | pm_cont | admin_cont | analyst_cont |
|-----------|----------|---------|-----------|-------------|---------|-----------|-------------|
| subsystem.view | Просмотр | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| subsystem.create | Создание | ✓ | ✗ | ~(1) | ✓ | ✗ | ~(1) |
| subsystem.edit | Редактирование | ✓ | ✗ | ~(1) | ✓ | ✗ | ~(1) |
| subsystem.delete | Удаление | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| subsystem.reorder | Изменение порядка | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |

## Catalog Service — Функции (7 permissions)

| Permission | Описание | pm_cust | admin_cust | analyst_cust | pm_cont | admin_cont | analyst_cont |
|-----------|----------|---------|-----------|-------------|---------|-----------|-------------|
| function.view | Просмотр | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| function.create | Создание | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| function.edit_info | Редактирование описания, требований, тестов | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| function.edit_cost | Редактирование стоимостных параметров | ✓ | ✗ | ✗ | ✓ | ✗ | ~(2) |
| function.edit_priority | Изменение приоритета (MoSCoW) | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| function.move | Перенос между подсистемами | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| function.delete | Soft delete | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |

## Catalog Service — Ставки (2 permissions)

| Permission | Описание | pm_cust | admin_cust | analyst_cust | pm_cont | admin_cont | analyst_cont |
|-----------|----------|---------|-----------|-------------|---------|-----------|-------------|
| rates.view | Просмотр | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| rates.edit | Изменение | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |

## Catalog Service — Шаблоны (4 permissions)

| Permission | Описание | pm_cust | admin_cust | analyst_cust | pm_cont | admin_cont | analyst_cont |
|-----------|----------|---------|-----------|-------------|---------|-----------|-------------|
| template.view | Просмотр | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| template.create | Создание | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| template.edit | Редактирование (новая версия) | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| template.delete | Удаление (запрещено для is_system) | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |

## Catalog Service — Документы (4 permissions)

| Permission | Описание | pm_cust | admin_cust | analyst_cust | pm_cont | admin_cont | analyst_cont |
|-----------|----------|---------|-----------|-------------|---------|-----------|-------------|
| document.view | Просмотр | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| document.create | Создание из шаблона | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| document.edit | Редактирование (если draft/revision) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| document.delete | Удаление | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |

## Workflow Service (8 permissions)

| Permission | Описание | pm_cust | admin_cust | analyst_cust | pm_cont | admin_cont | analyst_cont |
|-----------|----------|---------|-----------|-------------|---------|-----------|-------------|
| approval.submit | Отправить на согласование | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| approval.decide_tz | Финальное решение по ТЗ/ЧТЗ/ПМИ | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| approval.decide_nmck | Финальное решение по НМЦК | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| approval.review | Рецензия (информативная) | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| approval.revoke | Отзыв своего решения | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| approval.cancel | Отмена согласования | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| approval.view | Просмотр | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| approval.view_history | История раундов | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## Примечания

**(1) «Предложить»** — аналитик может отправить изменение подсистемы как предложение, которое требует подтверждения РП. В MVP упрощено: аналитик оставляет комментарий, РП вносит изменение.

**(2) «Предложить стоимость»** — аналитик подрядчика может предложить изменение cost_params. В MVP: аналитик оставляет комментарий к функции, РП вносит изменение.

## Итого

- **38 permissions** (8 Auth + 22 Catalog + 8 Workflow)
- **3 проектные роли** × 2 стороны = 6 контекстных ролей
- **1 глобальная роль** (superadmin)
- Администратор управляет только **своей стороной**
- РП согласует, администратор **не согласует**
- Аналитик рецензирует, но **не принимает финальных решений**
