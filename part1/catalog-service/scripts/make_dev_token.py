"""
Генерирует тестовый JWT и выводит его в консоль.
Используется для ручного тестирования через Swagger UI без запущенного Auth Service.

Запуск (из директории catalog-service/):
    docker exec catalog-service python3 scripts/make_dev_token.py [role] [side]

Аргументы:
    role  — pm | admin | analyst  (по умолчанию: pm)
    side  — customer | contractor  (по умолчанию: customer)

Примеры:
    docker exec catalog-service python3 scripts/make_dev_token.py
    docker exec catalog-service python3 scripts/make_dev_token.py analyst contractor
"""
from __future__ import annotations
import sys
import time
import os
import json
from pathlib import Path

KEY_DIR = Path("/keys")
PRIVATE_KEY_PATH = KEY_DIR / "jwt_private.pem"
PUBLIC_KEY_PATH = KEY_DIR / "jwt_public.pem"

PROJECT_ID = "aaaaaaaa-0000-0000-0000-000000000001"
USER_ID    = "bbbbbbbb-0000-0000-0000-000000000001"
ORG_ID     = "cccccccc-0000-0000-0000-000000000001"

role = sys.argv[1] if len(sys.argv) > 1 else "pm"
side = sys.argv[2] if len(sys.argv) > 2 else "customer"


def ensure_keys():
    KEY_DIR.mkdir(exist_ok=True)
    if not PRIVATE_KEY_PATH.exists():
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, PublicFormat, NoEncryption,
        )
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        PRIVATE_KEY_PATH.write_bytes(
            key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())
        )
        PUBLIC_KEY_PATH.write_bytes(
            key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        )
        print(f"[keys generated] {PRIVATE_KEY_PATH}", file=sys.stderr)
    else:
        print(f"[keys exist] {PRIVATE_KEY_PATH}", file=sys.stderr)


ensure_keys()

import jwt as pyjwt

private_key = PRIVATE_KEY_PATH.read_text()
payload = {
    "sub":          USER_ID,
    "org_id":       ORG_ID,
    "is_superadmin": False,
    "roles": [{"project_id": PROJECT_ID, "role": role, "side": side}],
    "iat": int(time.time()),
    "exp": int(time.time()) + 86400,  # 24 часа
}

token = pyjwt.encode(payload, private_key, algorithm="RS256")

print("\n" + "="*60)
print(f"  role={role}  side={side}  (24 часа)")
print("="*60)
print(token)
print("="*60)
print(f"\n  PROJECT_ID : {PROJECT_ID}")
print(f"  USER_ID    : {USER_ID}")
print(f"\n  Вставить в Swagger: Authorize → Bearer <token>")
print()
print(f"  PUBLIC_KEY : {PUBLIC_KEY_PATH}")
print("  Убедитесь что контейнер запущен с:")
print(f"    JWT_PUBLIC_KEY_PATH={PUBLIC_KEY_PATH}")
print("    JWKS_URL=")
print()
