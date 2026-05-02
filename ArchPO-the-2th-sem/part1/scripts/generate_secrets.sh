#!/bin/bash
# Генерирует RSA ключи для JWT и создаёт .env из .env.example
# Запускать один раз перед первым docker-compose up

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SECRETS_DIR="$ROOT_DIR/secrets"

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
    echo "  ✓ .env создан — заполните реальные значения перед деплоем"
else
    echo "  → .env уже существует, пропускаю"
fi

echo ""
echo "=== Готово ==="
echo "Теперь можно запускать: docker-compose up --build"
