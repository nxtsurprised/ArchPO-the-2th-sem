#!/usr/bin/env bash
# ============================================================
# seed_demo.sh — Наполнение демо-данными для локального запуска
#
# Создаёт:
#   - 2 организации: ООО Заказчик + ООО Подрядчик
#   - Суперадмин: admin@demo.local / Admin@Demo2024!
#   - Пользователи: pm_customer@demo.local, pm_contractor@demo.local
#   - Проект: DEMO-2024
#   - 4 функции в справочнике
#   - ТЗ документ с содержимым (для контекста PMI-агента)
#   - Пустой ПМИ документ (для генерации агентом)
#
# Использование:
#   cd ArchPO-the-2th-sem/part1
#   bash scripts/seed_demo.sh
#
# Требования: docker compose запущен, jq установлен
# ============================================================

set -euo pipefail

# ── Конфигурация ──────────────────────────────────────────────
AUTH_URL="http://localhost:8001"
CATALOG_URL="http://localhost:8002"
DEMO_PASSWORD="Demo@Pass2024!"
ADMIN_PASSWORD="Admin@Demo2024!"

# ── Утилиты ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

# Все log_* пишут в stderr — не мешают захвату stdout через $()
log_info()    { echo -e "${GREEN}[INFO]${NC} $*" >&2; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
log_section() { echo -e "\n${YELLOW}══ $* ══${NC}" >&2; }

check_deps() {
    command -v docker &>/dev/null || log_error "docker не найден"
    command -v jq     &>/dev/null || log_error "jq не найден (brew install jq / apt install jq)"
    command -v curl   &>/dev/null || log_error "curl не найден"
}

wait_service() {
    local url="$1" name="$2" max_tries=30 i=0
    log_info "Ожидание $name..."
    while ! curl -sf "$url/health" >/dev/null 2>&1; do
        i=$((i + 1))
        [[ $i -ge $max_tries ]] && log_error "$name не отвечает после ${max_tries}s"
        sleep 1
    done
    log_info "$name готов"
}

# api_call METHOD URL [curl-args...] — возвращает тело ответа в stdout
# При HTTP >= 400 выводит предупреждение в stderr и возвращает exit 1
api_call() {
    local method="$1" url="$2"; shift 2
    local resp http_code body
    resp=$(curl -s -X "$method" "$url" \
        -H "Content-Type: application/json" \
        "$@" \
        -w '\n%{http_code}' 2>/dev/null) || true

    http_code=$(echo "$resp" | tail -1)
    body=$(echo "$resp" | sed '$d')

    if [[ -n "$http_code" && "$http_code" -ge 400 ]]; then
        log_warn "HTTP $http_code для $method $url"
        log_warn "Ответ: $body"
        echo "$body"
        return 1
    fi
    echo "$body"
}

# ── Шаг 0: Проверки ───────────────────────────────────────────
log_section "Проверка зависимостей"
check_deps

docker compose ps --services 2>/dev/null | grep -q "auth-service" \
    || log_error "docker compose не запущен. Выполните: docker compose up -d"

# ── Шаг 1: Ждём сервисы ───────────────────────────────────────
log_section "Ожидание сервисов"
wait_service "$AUTH_URL"    "auth-service"
wait_service "$CATALOG_URL" "catalog-service"

# ── Шаг 2: Bootstrap суперадмина ─────────────────────────────
log_section "Bootstrap суперадмина (через контейнер)"

BOOTSTRAP_OUTPUT=$(docker compose exec -T auth-service python << 'PYEOF'
import asyncio, sys
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

sys.path.insert(0, '/app')

from app.models.user import Organization, User
from app.services.password import hash_password
from app.config import get_settings

settings = get_settings()

async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        CUST_INN = "7700000001"
        cust_org = (await session.execute(
            select(Organization).where(Organization.inn == CUST_INN)
        )).scalar_one_or_none()

        if cust_org is None:
            cust_org = Organization(
                name="ООО Заказчик (demo)",
                inn=CUST_INN,
                ogrn="1027700000001",
                legal_address="г. Москва, ул. Демо, д. 1",
            )
            session.add(cust_org)
            await session.flush()
            print(f"CUST_ORG_CREATED:{cust_org.id}", flush=True)
        else:
            print(f"CUST_ORG_EXISTS:{cust_org.id}", flush=True)

        ADMIN_EMAIL = "admin@demo.local"
        admin = (await session.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )).scalar_one_or_none()

        if admin is None:
            admin = User(
                email=ADMIN_EMAIL,
                password_hash=hash_password("Admin@Demo2024!"),
                full_name="Системный Администратор",
                position="Администратор",
                organization_id=cust_org.id,
                is_superadmin=True,
                password_expires_at=(
                    datetime.now(timezone.utc) + timedelta(days=365)
                ).replace(tzinfo=None),
            )
            session.add(admin)
            await session.flush()
            print(f"ADMIN_CREATED:{admin.id}", flush=True)
        else:
            print(f"ADMIN_EXISTS:{admin.id}", flush=True)

        await session.commit()

    await engine.dispose()

asyncio.run(main())
PYEOF
)

log_info "Bootstrap: $BOOTSTRAP_OUTPUT"

CUST_ORG_ID=$(echo "$BOOTSTRAP_OUTPUT" | grep -oE 'CUST_ORG_(CREATED|EXISTS):[0-9a-f-]+' | awk -F: '{print $2}')
[[ -z "$CUST_ORG_ID" ]] && log_error "Не удалось получить ID организации заказчика"
log_info "ID организации заказчика: $CUST_ORG_ID"

# ── Шаг 3: Логин суперадмина ──────────────────────────────────
log_section "Логин суперадмина"

LOGIN_RESP=$(api_call POST "$AUTH_URL/api/auth/login" \
    -d "{\"email\":\"admin@demo.local\",\"password\":\"$ADMIN_PASSWORD\"}")
ADMIN_TOKEN=$(echo "$LOGIN_RESP" | jq -r '.access_token // empty')
[[ -z "$ADMIN_TOKEN" ]] && log_error "Не удалось получить токен суперадмина. Ответ: $LOGIN_RESP"
log_info "Токен суперадмина получен"

AUTH_HEADER="Authorization: Bearer $ADMIN_TOKEN"

# ── Шаг 4: Создание организации подрядчика ────────────────────
log_section "Создание организации подрядчика"

CONTR_RESP=$(api_call GET "$AUTH_URL/api/auth/organizations?per_page=100" \
    -H "$AUTH_HEADER" || echo '{"items":[]}')
CONTR_ORG_ID=$(echo "$CONTR_RESP" | jq -r '.items[] | select(.inn=="7700000002") | .id' | head -1)

if [[ -z "$CONTR_ORG_ID" ]]; then
    CREATE_CONTR=$(api_call POST "$AUTH_URL/api/auth/organizations" \
        -H "$AUTH_HEADER" \
        -d '{"name":"ООО Подрядчик (demo)","inn":"7700000002","ogrn":"1027700000002","legal_address":"г. Москва, ул. Демо, д. 2"}')
    CONTR_ORG_ID=$(echo "$CREATE_CONTR" | jq -r '.id')
    log_info "Организация подрядчика создана: $CONTR_ORG_ID"
else
    log_info "Организация подрядчика уже существует: $CONTR_ORG_ID"
fi

# ── Шаг 5: Создание проекта ───────────────────────────────────
log_section "Создание проекта"

PROJECTS_RESP=$(api_call GET "$AUTH_URL/api/auth/projects?per_page=100" \
    -H "$AUTH_HEADER" || echo '{"items":[]}')
PROJECT_ID=$(echo "$PROJECTS_RESP" | jq -r '.items[] | select(.code=="DEMO-2024") | .id' | head -1)

if [[ -z "$PROJECT_ID" ]]; then
    CREATE_PROJ=$(api_call POST "$AUTH_URL/api/auth/projects" \
        -H "$AUTH_HEADER" \
        -d "{\"code\":\"DEMO-2024\",\"name\":\"Демонстрационный проект ГОСТ 34\",\"customer_org_id\":\"$CUST_ORG_ID\",\"contractor_org_id\":\"$CONTR_ORG_ID\"}")
    PROJECT_ID=$(echo "$CREATE_PROJ" | jq -r '.id')
    log_info "Проект создан: $PROJECT_ID"
else
    log_info "Проект уже существует: $PROJECT_ID"
fi

# ── Шаг 6: Создание пользователей ────────────────────────────
log_section "Создание пользователей"

# Получаем список пользователей один раз (max per_page = 100)
USERS_LIST=$(api_call GET "$AUTH_URL/api/auth/users?per_page=100" -H "$AUTH_HEADER" || echo '{"items":[]}')

create_user_if_absent() {
    local email="$1" full_name="$2" position="$3" org_id="$4"
    local user_id

    # Ищем в уже загруженном списке
    user_id=$(echo "$USERS_LIST" | jq -r --arg e "$email" '.items[] | select(.email==$e) | .id' | head -1)

    if [[ -z "$user_id" ]]; then
        local create_resp http_status
        # Пробуем создать
        create_resp=$(api_call POST "$AUTH_URL/api/auth/users" \
            -H "$AUTH_HEADER" \
            -d "{\"email\":\"$email\",\"password\":\"$DEMO_PASSWORD\",\"full_name\":\"$full_name\",\"position\":\"$position\",\"organization_id\":\"$org_id\"}") || true

        user_id=$(echo "$create_resp" | jq -r '.id // empty' 2>/dev/null)

        if [[ -z "$user_id" ]]; then
            # Пользователь уже существует (409) — ищем по email через повторный запрос
            local fresh
            fresh=$(api_call GET "$AUTH_URL/api/auth/users?per_page=100" -H "$AUTH_HEADER" || echo '{"items":[]}')
            user_id=$(echo "$fresh" | jq -r --arg e "$email" '.items[] | select(.email==$e) | .id' | head -1)
            log_info "Пользователь уже существует: $email ($user_id)"
        else
            log_info "Пользователь создан: $email ($user_id)"
        fi
    else
        log_info "Пользователь уже существует: $email ($user_id)"
    fi
    printf '%s' "$user_id"
}

PM_CUST_ID=$(create_user_if_absent "pm_customer@demo.local"  "Петров Пётр Петрович"      "Руководитель проекта" "$CUST_ORG_ID")
PM_CONTR_ID=$(create_user_if_absent "pm_contractor@demo.local" "Сидоров Сидор Сидорович" "Руководитель проекта" "$CONTR_ORG_ID")
ANALYST_ID=$(create_user_if_absent "analyst@demo.local"      "Иванова Анна Ивановна"     "Аналитик"             "$CONTR_ORG_ID")

# ── Шаг 7: Назначение ролей ───────────────────────────────────
log_section "Назначение ролей в проекте"

assign_role() {
    local user_id="$1" role_name="$2"
    api_call PATCH "$AUTH_URL/api/auth/users/$user_id/roles" \
        -H "$AUTH_HEADER" \
        -d "{\"project_id\":\"$PROJECT_ID\",\"role_name\":\"$role_name\"}" >/dev/null 2>&1 || true
    log_info "Роль $role_name → $user_id"
}

assign_role "$PM_CUST_ID"  "pm"
assign_role "$PM_CONTR_ID" "pm"
assign_role "$ANALYST_ID"  "analyst"

# ── Шаг 8: Создание функций ───────────────────────────────────
log_section "Создание функций в справочнике"

# Используем суперадмина — он проходит require_project_role для любого проекта
# Получаем список функций один раз
FN_LIST=$(api_call GET "$CATALOG_URL/api/catalog/functions?project_id=$PROJECT_ID&per_page=100" \
    -H "$AUTH_HEADER" || echo '{"items":[]}')

create_function_if_absent() {
    local code="$1" name="$2" description="$3" criteria="$4"
    local fn_id

    fn_id=$(echo "$FN_LIST" | jq -r --arg c "$code" '.items[] | select(.code==$c) | .id' | head -1)

    if [[ -z "$fn_id" ]]; then
        local body create_resp
        body=$(jq -n \
            --arg pid "$PROJECT_ID" \
            --arg code "$code" \
            --arg name "$name" \
            --arg desc "$description" \
            --argjson crit "$criteria" \
            '{project_id:$pid,code:$code,name:$name,description:$desc,category:"main",priority:"high",complexity:"medium",test_params:{approach:"automated",criteria:$crit}}')
        create_resp=$(api_call POST "$CATALOG_URL/api/catalog/functions" -H "$AUTH_HEADER" -d "$body")
        fn_id=$(echo "$create_resp" | jq -r '.id // empty' 2>/dev/null)
        log_info "Функция создана: $code ($fn_id)"
    else
        log_info "Функция уже существует: $code ($fn_id)"
    fi
    printf '%s' "$fn_id"
}

FN1_ID=$(create_function_if_absent "F-AUTH-01" \
    "Аутентификация пользователя" \
    "Аутентификация по логину и паролю с поддержкой 2FA (TOTP). Блокировка после 5 неудачных попыток на 30 минут." \
    '[{"id":"c1","text":"Успешный вход при корректных credentials"},{"id":"c2","text":"Блокировка после 5 неверных попыток"},{"id":"c3","text":"2FA через TOTP работает корректно"}]')

FN2_ID=$(create_function_if_absent "F-DOC-01" \
    "Создание и редактирование документа" \
    "Создание документов ТЗ, ЧТЗ, ПМИ, НМЦК на основе шаблонов с привязкой к проекту и функциям." \
    '[{"id":"c1","text":"Создание документа любого поддерживаемого типа"},{"id":"c2","text":"Версия документа инкрементируется при сохранении"},{"id":"c3","text":"Пользователь без роли не может создать документ"}]')

FN3_ID=$(create_function_if_absent "F-WF-01" \
    "Согласование документа" \
    "Многораундовое согласование: каждый раунд завершается после решений обоих РП. Решения: approved, revision, rejected." \
    '[{"id":"c1","text":"После запуска документ переходит в статус pending"},{"id":"c2","text":"Оба РП должны принять решение для завершения раунда"},{"id":"c3","text":"При revision документ возвращается на доработку"}]')

FN4_ID=$(create_function_if_absent "F-GEN-01" \
    "Генерация .docx файла" \
    "Генерация документа .docx по шаблону .dotx. Файл сохраняется в MinIO, доступен по presigned URL на 15 минут." \
    '[{"id":"c1","text":"Документ открывается в Word без ошибок"},{"id":"c2","text":"Presigned URL истекает через 15 минут"},{"id":"c3","text":"Все разделы заполнены по справочнику функций"}]')

ALL_FN_IDS=$(jq -n --arg a "$FN1_ID" --arg b "$FN2_ID" --arg c "$FN3_ID" --arg d "$FN4_ID" '[$a,$b,$c,$d]')

# ── Шаг 9: Шаблоны документов ────────────────────────────────
log_section "Создание системных шаблонов"

# Создаём шаблон ПМИ если его нет (суперадмин = разрешено создавать системные шаблоны)
TMPl_CHECK=$(api_call GET "$CATALOG_URL/api/catalog/templates?type=pmi" \
    -H "$AUTH_HEADER" || echo '{"items":[]}')
PMI_TMPL_ID=$(echo "$TMPl_CHECK" | jq -r '.items[] | select(.name=="ПМИ по ГОСТ 34.603 (демо)") | .id' | head -1)

if [[ -z "$PMI_TMPL_ID" ]]; then
    PMI_TMPL_BODY=$(cat << 'JSONEOF'
{
  "type": "pmi",
  "name": "ПМИ по ГОСТ 34.603 (демо)",
  "gost_ref": "ГОСТ 34.603-92",
  "output_format": "docx",
  "sections": [
    {
      "number": "1",
      "title": "Объект испытаний",
      "source": "manual",
      "fields": [
        {"key": "system_name",    "label": "Наименование АС",       "type": "text",     "required": true},
        {"key": "version",        "label": "Версия",                "type": "text",     "required": false},
        {"key": "test_basis",     "label": "Основание для испытаний","type": "textarea", "required": false}
      ]
    },
    {
      "number": "2",
      "title": "Цель испытаний",
      "source": "manual",
      "fields": [
        {"key": "goal", "label": "Цель", "type": "textarea", "required": true}
      ]
    },
    {
      "number": "3",
      "title": "Условия проведения испытаний",
      "source": "manual",
      "fields": [
        {"key": "environment",    "label": "Программно-аппаратная среда", "type": "textarea", "required": false},
        {"key": "participants",   "label": "Участники испытаний",         "type": "textarea", "required": false},
        {"key": "test_data_desc", "label": "Тестовые данные",             "type": "textarea", "required": false}
      ]
    },
    {
      "number": "4",
      "title": "Перечень проверяемых функций",
      "source": "functions"
    },
    {
      "number": "5",
      "title": "Порядок проведения испытаний",
      "source": "manual",
      "fields": [
        {"key": "procedure", "label": "Порядок испытаний", "type": "textarea", "required": false}
      ]
    },
    {
      "number": "6",
      "title": "Требования к отчётности",
      "source": "manual",
      "fields": [
        {"key": "report_requirements", "label": "Требования к протоколу испытаний", "type": "textarea", "required": false}
      ]
    }
  ]
}
JSONEOF
)
    PMI_TMPL_RESP=$(api_call POST "$CATALOG_URL/api/catalog/templates" \
        -H "$AUTH_HEADER" -d "$PMI_TMPL_BODY")
    PMI_TMPL_ID=$(echo "$PMI_TMPL_RESP" | jq -r '.id // empty' 2>/dev/null)
    log_info "Шаблон ПМИ создан: $PMI_TMPL_ID"
else
    log_info "Шаблон ПМИ уже существует: $PMI_TMPL_ID"
fi

# ── Шаг 10: ТЗ документ ───────────────────────────────────────
log_section "Создание ТЗ документа"

TZ_CHECK=$(api_call GET "$CATALOG_URL/api/catalog/documents?project_id=$PROJECT_ID&type=tz&per_page=20" \
    -H "$AUTH_HEADER" || echo '{"items":[]}')
TZ_DOC_ID=$(echo "$TZ_CHECK" | jq -r 'if .items | length > 0 then .items[0].id else "" end')

if [[ -z "$TZ_DOC_ID" ]]; then
    TZ_BODY=$(jq -n \
        --arg pid "$PROJECT_ID" \
        --argjson fns "$ALL_FN_IDS" \
        '{
            project_id: $pid,
            name: "Техническое задание на разработку АС ГОСТ 34",
            type: "tz",
            function_ids: $fns,
            data: {
                sections: {
                    general: {
                        full_name: "Автоматизированная система формирования документации по ГОСТ 34",
                        short_name: "АС ГОСТ-ДОК",
                        document_basis: "Государственный контракт №123/2024 от 01.01.2024",
                        planned_completion: "31.12.2024"
                    },
                    purpose: "Система предназначена для автоматизации формирования и согласования документации по ГОСТ 34.",
                    requirements: {
                        functional: "1. Аутентификация с 2FA\n2. Справочник функций\n3. Генерация ТЗ/ЧТЗ/ПМИ/НМЦК\n4. Многораундовое согласование\n5. Аудит операций",
                        security: "Argon2id для паролей, AES-256 для ПДн, RBAC (7 ролей), блокировка после 5 неудачных попыток.",
                        performance: "API: не более 500 мс (p95). Генерация .docx: не более 10 секунд."
                    },
                    acceptance_criteria: "Все функции покрыты тестами ПМИ. Протокол по ГОСТ 34.603."
                }
            }
        }')
    TZ_RESP=$(api_call POST "$CATALOG_URL/api/catalog/documents" -H "$AUTH_HEADER" -d "$TZ_BODY")
    TZ_DOC_ID=$(echo "$TZ_RESP" | jq -r '.id')
    log_info "ТЗ документ создан: $TZ_DOC_ID"
else
    log_info "ТЗ документ уже существует: $TZ_DOC_ID"
fi

# ── Шаг 11: ПМИ документ ──────────────────────────────────────
log_section "Создание ПМИ документа"

PMI_CHECK=$(api_call GET "$CATALOG_URL/api/catalog/documents?project_id=$PROJECT_ID&type=pmi&per_page=20" \
    -H "$AUTH_HEADER" || echo '{"items":[]}')
PMI_DOC_ID=$(echo "$PMI_CHECK" | jq -r 'if .items | length > 0 then .items[0].id else "" end')

if [[ -z "$PMI_DOC_ID" ]]; then
    PMI_BODY=$(jq -n \
        --arg pid "$PROJECT_ID" \
        --arg tmpl "$PMI_TMPL_ID" \
        --argjson fns "$ALL_FN_IDS" \
        '{project_id:$pid,name:"Программа и методика испытаний АС ГОСТ-ДОК",type:"pmi",template_id:$tmpl,function_ids:$fns,data:{sections:{"1":{system_name:"АС ГОСТ-ДОК",version:"1.0",test_basis:"Государственный контракт №123/2024"},"2":{goal:"Проверка соответствия реализованных функций требованиям ТЗ по ГОСТ 34.603-92."},"3":{environment:"Docker Compose, Ubuntu 22.04, Python 3.12, PostgreSQL 16, MongoDB 7, MinIO"}}}}')
    PMI_RESP=$(api_call POST "$CATALOG_URL/api/catalog/documents" -H "$AUTH_HEADER" -d "$PMI_BODY")
    PMI_DOC_ID=$(echo "$PMI_RESP" | jq -r '.id')
    log_info "ПМИ документ создан: $PMI_DOC_ID"
else
    # Проверяем: если документ уже существует но без шаблона — патчим template_id
    EXISTING_TMPL=$(echo "$PMI_CHECK" | jq -r 'if .items | length > 0 then .items[0].template_id else "" end')
    if [[ -z "$EXISTING_TMPL" || "$EXISTING_TMPL" == "null" ]] && [[ -n "$PMI_TMPL_ID" ]]; then
        api_call PUT "$CATALOG_URL/api/catalog/documents/$PMI_DOC_ID" \
            -H "$AUTH_HEADER" \
            -d "{\"template_id\":\"$PMI_TMPL_ID\"}" >/dev/null || true
        log_info "ПМИ документ обновлён: template_id=$PMI_TMPL_ID"
    else
        log_info "ПМИ документ уже существует: $PMI_DOC_ID"
    fi
fi

# ── Итог ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ДЕМО-ДАННЫЕ УСПЕШНО СОЗДАНЫ                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${YELLOW}Адрес системы:${NC}   http://localhost:8080"
echo ""
echo -e "  ${YELLOW}Суперадмин:${NC}      admin@demo.local / Admin@Demo2024!"
echo -e "  ${YELLOW}РП заказчика:${NC}    pm_customer@demo.local / $DEMO_PASSWORD"
echo -e "  ${YELLOW}РП подрядчика:${NC}   pm_contractor@demo.local / $DEMO_PASSWORD"
echo -e "  ${YELLOW}Аналитик:${NC}        analyst@demo.local / $DEMO_PASSWORD"
echo ""
echo -e "  ${YELLOW}Проект:${NC}          DEMO-2024  (ID: $PROJECT_ID)"
echo -e "  ${YELLOW}Функции:${NC}         F-AUTH-01  F-DOC-01  F-WF-01  F-GEN-01"
echo -e "  ${YELLOW}ТЗ документ:${NC}     $TZ_DOC_ID"
echo -e "  ${YELLOW}ПМИ документ:${NC}    $PMI_DOC_ID"
echo ""
echo -e "  ${YELLOW}Для генерации ПМИ:${NC}"
echo -e "    http://localhost:8080 → войти как pm_contractor"
echo -e "    → Проект DEMO-2024 → Документы → ПМИ → «Составить ПМИ»"
echo ""
