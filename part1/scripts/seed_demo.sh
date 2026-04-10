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

log_info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
log_section() { echo -e "\n${YELLOW}══ $* ══${NC}"; }

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

api_call() {
    # api_call METHOD URL [-H header] [-d body] — возвращает JSON тела ответа
    # Завершается ошибкой при HTTP >= 400
    local method="$1" url="$2"; shift 2
    local resp
    resp=$(curl -sf -X "$method" "$url" \
        -H "Content-Type: application/json" \
        "$@" \
        -w '\n%{http_code}' 2>&1) || true

    local body http_code
    http_code=$(echo "$resp" | tail -1)
    body=$(echo "$resp" | head -n -1)

    if [[ "$http_code" -ge 400 ]]; then
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

# Проверяем, что docker compose запущен
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

import sys
sys.path.insert(0, '/app')

from app.models.user import Organization, User
from app.services.password import hash_password
from app.config import get_settings

settings = get_settings()

async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # Создаём организацию заказчика
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

        # Создаём суперадмина
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

log_info "Bootstrap вывод: $BOOTSTRAP_OUTPUT"

CUST_ORG_ID=$(echo "$BOOTSTRAP_OUTPUT" | grep -oP '(?<=CUST_ORG_(?:CREATED|EXISTS):)[0-9a-f-]+')
[[ -z "$CUST_ORG_ID" ]] && log_error "Не удалось получить ID организации заказчика"
log_info "ID организации заказчика: $CUST_ORG_ID"

# ── Шаг 3: Логин суперадмина ──────────────────────────────────
log_section "Логин суперадмина"

LOGIN_RESP=$(api_call POST "$AUTH_URL/api/auth/login" \
    -d "{\"email\":\"admin@demo.local\",\"password\":\"$ADMIN_PASSWORD\"}")
ADMIN_TOKEN=$(echo "$LOGIN_RESP" | jq -r '.access_token')
[[ -z "$ADMIN_TOKEN" || "$ADMIN_TOKEN" == "null" ]] && log_error "Не удалось получить токен суперадмина"
log_info "Токен суперадмина получен"

AUTH_HEADER="Authorization: Bearer $ADMIN_TOKEN"

# ── Шаг 4: Создание организации подрядчика ────────────────────
log_section "Создание организации подрядчика"

# Проверяем, есть ли уже подрядчик
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
        -d "{
            \"code\": \"DEMO-2024\",
            \"name\": \"Демонстрационный проект ГОСТ 34\",
            \"customer_org_id\": \"$CUST_ORG_ID\",
            \"contractor_org_id\": \"$CONTR_ORG_ID\"
        }")
    PROJECT_ID=$(echo "$CREATE_PROJ" | jq -r '.id')
    log_info "Проект создан: $PROJECT_ID"
else
    log_info "Проект уже существует: $PROJECT_ID"
fi

# ── Шаг 6: Создание пользователей ────────────────────────────
log_section "Создание пользователей"

create_user_if_absent() {
    local email="$1" full_name="$2" position="$3" org_id="$4"
    local check_resp user_id

    check_resp=$(api_call GET "$AUTH_URL/api/auth/users?per_page=200" \
        -H "$AUTH_HEADER" || echo '{"items":[]}')
    user_id=$(echo "$check_resp" | jq -r --arg e "$email" '.items[] | select(.email==$e) | .id' | head -1)

    if [[ -z "$user_id" ]]; then
        local create_resp
        create_resp=$(api_call POST "$AUTH_URL/api/auth/users" \
            -H "$AUTH_HEADER" \
            -d "{
                \"email\": \"$email\",
                \"password\": \"$DEMO_PASSWORD\",
                \"full_name\": \"$full_name\",
                \"position\": \"$position\",
                \"organization_id\": \"$org_id\"
            }")
        user_id=$(echo "$create_resp" | jq -r '.id')
        log_info "Пользователь создан: $email ($user_id)"
    else
        log_info "Пользователь уже существует: $email ($user_id)"
    fi
    echo "$user_id"
}

PM_CUST_ID=$(create_user_if_absent \
    "pm_customer@demo.local" "Петров Пётр Петрович" "Руководитель проекта" "$CUST_ORG_ID")

PM_CONTR_ID=$(create_user_if_absent \
    "pm_contractor@demo.local" "Сидоров Сидор Сидорович" "Руководитель проекта" "$CONTR_ORG_ID")

ANALYST_ID=$(create_user_if_absent \
    "analyst@demo.local" "Иванова Анна Ивановна" "Аналитик" "$CONTR_ORG_ID")

# ── Шаг 7: Назначение ролей ───────────────────────────────────
log_section "Назначение ролей в проекте"

assign_role() {
    local user_id="$1" role_name="$2"
    api_call PATCH "$AUTH_URL/api/auth/users/$user_id/roles" \
        -H "$AUTH_HEADER" \
        -d "{\"project_id\":\"$PROJECT_ID\",\"role_name\":\"$role_name\"}" >/dev/null
    log_info "Роль $role_name назначена пользователю $user_id"
}

assign_role "$PM_CUST_ID"  "pm"
assign_role "$PM_CONTR_ID" "pm"
assign_role "$ANALYST_ID"  "analyst"

# Логинимся как pm_contractor, чтобы работать с каталогом
PM_TOKEN_RESP=$(api_call POST "$AUTH_URL/api/auth/login" \
    -d "{\"email\":\"pm_contractor@demo.local\",\"password\":\"$DEMO_PASSWORD\"}")
PM_TOKEN=$(echo "$PM_TOKEN_RESP" | jq -r '.access_token')
PM_AUTH="Authorization: Bearer $PM_TOKEN"

# ── Шаг 8: Создание функций ───────────────────────────────────
log_section "Создание функций в справочнике"

create_function_if_absent() {
    local code="$1" name="$2" description="$3" criteria="$4"

    # Проверяем наличие
    local check
    check=$(api_call GET "$CATALOG_URL/api/catalog/functions?project_id=$PROJECT_ID&per_page=100" \
        -H "$PM_AUTH" || echo '{"items":[]}')
    local fn_id
    fn_id=$(echo "$check" | jq -r --arg c "$code" '.items[] | select(.code==$c) | .id' | head -1)

    if [[ -z "$fn_id" ]]; then
        local body
        body=$(jq -n \
            --arg pid "$PROJECT_ID" \
            --arg code "$code" \
            --arg name "$name" \
            --arg desc "$description" \
            --argjson crit "$criteria" \
            '{
                project_id: $pid,
                code: $code,
                name: $name,
                description: $desc,
                category: "main",
                priority: "high",
                complexity: "medium",
                test_params: { approach: "automated", criteria: $crit }
            }')
        local create_resp
        create_resp=$(api_call POST "$CATALOG_URL/api/catalog/functions" \
            -H "$PM_AUTH" -d "$body")
        fn_id=$(echo "$create_resp" | jq -r '.id')
        log_info "Функция создана: $code ($fn_id)"
    else
        log_info "Функция уже существует: $code ($fn_id)"
    fi
    echo "$fn_id"
}

FN1_ID=$(create_function_if_absent \
    "F-AUTH-01" \
    "Аутентификация пользователя" \
    "Подсистема обеспечивает аутентификацию пользователей по логину и паролю с поддержкой двухфакторной аутентификации (TOTP). После 5 неудачных попыток аккаунт блокируется на 30 минут." \
    '[{"id":"c1","text":"Пользователь успешно аутентифицируется при вводе корректных credentials"},{"id":"c2","text":"При вводе неверного пароля 5 раз подряд аккаунт блокируется"},{"id":"c3","text":"Двухфакторная аутентификация через TOTP работает корректно"}]')

FN2_ID=$(create_function_if_absent \
    "F-DOC-01" \
    "Создание и редактирование документа" \
    "Система позволяет создавать документы типов ТЗ, ЧТЗ, ПМИ, НМЦК на основе шаблонов. Документ привязывается к проекту и набору функций. Поддерживается versioning." \
    '[{"id":"c1","text":"Пользователь может создать документ любого поддерживаемого типа"},{"id":"c2","text":"При сохранении версия документа инкрементируется"},{"id":"c3","text":"Пользователь без роли в проекте не может создать документ"}]')

FN3_ID=$(create_function_if_absent \
    "F-WF-01" \
    "Согласование документа" \
    "Запуск процесса согласования документа. Согласование многораундовое: каждый раунд завершается после решений обоих РП (заказчика и подрядчика). Поддерживаются решения: approved, revision, rejected." \
    '[{"id":"c1","text":"После запуска согласования документ переходит в статус pending"},{"id":"c2","text":"Оба РП должны принять решение для завершения раунда"},{"id":"c3","text":"При решении revision документ возвращается на доработку"}]')

FN4_ID=$(create_function_if_absent \
    "F-GEN-01" \
    "Генерация .docx файла" \
    "Система генерирует документ в формате .docx по шаблону .dotx с учётом данных из справочника функций. Файл сохраняется в MinIO и доступен по presigned URL на 15 минут." \
    '[{"id":"c1","text":"Сгенерированный документ открывается в Microsoft Word без ошибок"},{"id":"c2","text":"Presigned URL действует 15 минут и становится недоступен после истечения"},{"id":"c3","text":"Все разделы документа заполнены в соответствии со справочником функций"}]')

ALL_FN_IDS="[\"$FN1_ID\",\"$FN2_ID\",\"$FN3_ID\",\"$FN4_ID\"]"

# ── Шаг 9: ТЗ документ с содержимым ──────────────────────────
log_section "Создание ТЗ документа"

TZ_CHECK=$(api_call GET "$CATALOG_URL/api/catalog/documents?project_id=$PROJECT_ID&type=tz&per_page=20" \
    -H "$PM_AUTH" || echo '{"items":[]}')
TZ_DOC_ID=$(echo "$TZ_CHECK" | jq -r '.items[0].id // empty' | head -1)

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
                    purpose: "Система предназначена для автоматизации формирования, заполнения и согласования отчётной документации по ГОСТ 34 в рамках государственных контрактов между заказчиками и подрядчиками.",
                    requirements: {
                        functional: "1. Аутентификация пользователей с поддержкой 2FA (TOTP)\n2. Справочник функций как единый источник данных\n3. Генерация документов ТЗ, ЧТЗ, ПМИ, НМЦК\n4. Многораундовое согласование документов\n5. Полный журнал аудита всех операций",
                        security: "Система должна обеспечивать: хранение паролей в виде Argon2id-хешей, шифрование ПДн (AES-256), ролевое разграничение доступа (7 ролей), блокировку после 5 неудачных попыток входа.",
                        performance: "Время отклика API: не более 500 мс для 95% запросов. Генерация документа .docx: не более 10 секунд."
                    },
                    acceptance_criteria: "Все функции, указанные в справочнике, должны быть покрыты тестами ПМИ. Пройденные испытания подтверждаются протоколом ПМИ по ГОСТ 34.603."
                }
            }
        }')
    TZ_RESP=$(api_call POST "$CATALOG_URL/api/catalog/documents" \
        -H "$PM_AUTH" -d "$TZ_BODY")
    TZ_DOC_ID=$(echo "$TZ_RESP" | jq -r '.id')
    log_info "ТЗ документ создан: $TZ_DOC_ID"
else
    log_info "ТЗ документ уже существует: $TZ_DOC_ID"
fi

# ── Шаг 10: ПМИ документ ──────────────────────────────────────
log_section "Создание ПМИ документа"

PMI_CHECK=$(api_call GET "$CATALOG_URL/api/catalog/documents?project_id=$PROJECT_ID&type=pmi&per_page=20" \
    -H "$PM_AUTH" || echo '{"items":[]}')
PMI_DOC_ID=$(echo "$PMI_CHECK" | jq -r '.items[0].id // empty' | head -1)

if [[ -z "$PMI_DOC_ID" ]]; then
    PMI_BODY=$(jq -n \
        --arg pid "$PROJECT_ID" \
        --argjson fns "$ALL_FN_IDS" \
        '{
            project_id: $pid,
            name: "Программа и методика испытаний АС ГОСТ-ДОК",
            type: "pmi",
            function_ids: $fns,
            data: {}
        }')
    PMI_RESP=$(api_call POST "$CATALOG_URL/api/catalog/documents" \
        -H "$PM_AUTH" -d "$PMI_BODY")
    PMI_DOC_ID=$(echo "$PMI_RESP" | jq -r '.id')
    log_info "ПМИ документ создан: $PMI_DOC_ID"
else
    log_info "ПМИ документ уже существует: $PMI_DOC_ID"
fi

# ── Итог ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ДЕМО-ДАННЫЕ УСПЕШНО СОЗДАНЫ                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${YELLOW}Адрес системы:${NC}   http://localhost:8080"
echo ""
echo -e "  ${YELLOW}Суперадмин:${NC}"
echo -e "    Email:    admin@demo.local"
echo -e "    Пароль:   Admin@Demo2024!"
echo ""
echo -e "  ${YELLOW}РП заказчика:${NC}"
echo -e "    Email:    pm_customer@demo.local"
echo -e "    Пароль:   $DEMO_PASSWORD"
echo ""
echo -e "  ${YELLOW}РП подрядчика:${NC}"
echo -e "    Email:    pm_contractor@demo.local"
echo -e "    Пароль:   $DEMO_PASSWORD"
echo ""
echo -e "  ${YELLOW}Аналитик:${NC}"
echo -e "    Email:    analyst@demo.local"
echo -e "    Пароль:   $DEMO_PASSWORD"
echo ""
echo -e "  ${YELLOW}Проект:${NC}          DEMO-2024 (ID: $PROJECT_ID)"
echo -e "  ${YELLOW}Функции:${NC}         F-AUTH-01, F-DOC-01, F-WF-01, F-GEN-01"
echo -e "  ${YELLOW}ТЗ документ:${NC}     $TZ_DOC_ID"
echo -e "  ${YELLOW}ПМИ документ:${NC}    $PMI_DOC_ID"
echo ""
echo -e "  ${YELLOW}Для генерации ПМИ:${NC}"
echo -e "    Откройте http://localhost:8080, войдите как pm_contractor"
echo -e "    → Проект DEMO-2024 → Документы → ПМИ → «Составить ПМИ»"
echo ""
