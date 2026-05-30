#!/bin/bash
# Генерирует RSA ключи для JWT и создаёт .env из .env.example
# Запускать один раз перед первым docker-compose up

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SECRETS_DIR="$ROOT_DIR/secrets"

random_hex() {
    openssl rand -hex 24
}

fernet_key() {
    python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
}

set_env_value() {
    local key="$1"
    local value="$2"
    local file="$ROOT_DIR/.env"
    if grep -q "^${key}=" "$file"; then
        perl -0pi -e "s|^${key}=.*$|${key}=${value}|m" "$file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}

echo "=== Генерация секретов ==="

mkdir -p "$SECRETS_DIR"

# JWT RSA ключи
if [ ! -f "$SECRETS_DIR/jwt_private.pem" ]; then
    echo "→ Генерирую RSA-2048 ключевую пару..."
    openssl genrsa -out "$SECRETS_DIR/jwt_private.pem" 2048
    openssl rsa -in "$SECRETS_DIR/jwt_private.pem" -pubout -out "$SECRETS_DIR/jwt_public.pem"
    chmod 600 "$SECRETS_DIR/jwt_private.pem"
    echo "  ✓ jwt_private.pem, jwt_public.pem"
else
    echo "  → JWT ключи уже существуют, пропускаю"
fi

# .env из .env.example
if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "→ Создаю .env из .env.example..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    set_env_value "AUTH_DB_PASSWORD" "$(random_hex)"
    set_env_value "WORKFLOW_DB_PASSWORD" "$(random_hex)"
    set_env_value "CATALOG_MONGO_PASSWORD" "$(random_hex)"
    set_env_value "MINIO_SECRET_KEY" "$(random_hex)"
    set_env_value "INTERNAL_API_SECRET" "$(random_hex)"
    set_env_value "ENCRYPT_KEY_PHONE" "$(fernet_key)"
    set_env_value "ENCRYPT_KEY_TOTP" "$(fernet_key)"
    echo "  ✓ .env создан с локальными секретами"
else
    echo "  → .env уже существует, пропускаю"
    if grep -q "generate_me" "$ROOT_DIR/.env"; then
        echo "  → Обновляю плейсхолдеры ENCRYPT_KEY_* на валидные Fernet-ключи"
        set_env_value "ENCRYPT_KEY_PHONE" "$(fernet_key)"
        set_env_value "ENCRYPT_KEY_TOTP" "$(fernet_key)"
    fi
fi

echo ""
echo "=== Готово ==="
echo "Теперь можно запускать: bash scripts/deploy.sh -t coursework"
