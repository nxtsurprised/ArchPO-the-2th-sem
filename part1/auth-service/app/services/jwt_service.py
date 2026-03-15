from __future__ import annotations
import uuid
import hashlib
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
import jwt
from app.config import get_settings


def _load_private_key() -> str:
    """Читает приватный RSA-ключ из файла. Путь задаётся через JWT_PRIVATE_KEY_PATH."""
    return Path(get_settings().JWT_PRIVATE_KEY_PATH).read_text()


def _load_public_key() -> str:
    """Читает публичный RSA-ключ. Используется для JWKS-эндпоинта."""
    return Path(get_settings().JWT_PUBLIC_KEY_PATH).read_text()


def create_access_token(
    user_id: str,
    org_id: str,
    roles: list[dict],
    is_superadmin: bool = False,
) -> tuple[str, int]:
    """
    Выпускает JWT access-токен, подписанный приватным ключом RS256.

    Возвращает (token_string, exp_timestamp).

    Payload:
      sub          – UUID пользователя (стандартное поле JWT)
      org_id       – UUID организации
      roles        – список { project_id, role, side } для проверки прав в сервисах
      is_superadmin – флаг надпроектного доступа
      iat / exp    – время выпуска и срок жизни
      jti          – уникальный ID токена (для будущего blacklist)
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=settings.JWT_ACCESS_TTL_SECONDS)  # по умолчанию 15 минут

    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "roles": roles,
        "is_superadmin": is_superadmin,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid.uuid4()),  # JWT ID – каждый токен уникален
    }

    token = jwt.encode(payload, _load_private_key(), algorithm="RS256")
    return token, int(exp.timestamp())


def create_refresh_token() -> tuple[str, str]:
    """
    Генерирует пару (raw_token, sha256_hash).

    raw_token – UUID4, отдаётся клиенту в httpOnly cookie.
    sha256_hash – сохраняется в БД. Хранение хеша (а не самого токена)
    означает, что утечка БД не позволяет злоумышленнику использовать токены.
    """
    raw = str(uuid.uuid4())
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def get_jwks() -> dict:
    """
    Формирует JWKS (JSON Web Key Set) с публичным ключом RS256.

    Эндпоинт /.well-known/jwks.json публичен и кешируется другими сервисами
    на 1 час. Структура ответа соответствует RFC 7517.

    n и e – модуль и публичная экспонента RSA в base64url-кодировании без padding.
    """
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

    public_key_pem = _load_public_key()
    public_key = load_pem_public_key(public_key_pem.encode())

    if not isinstance(public_key, RSAPublicKey):
        raise ValueError("Expected RSA public key")

    pub_numbers = public_key.public_numbers()

    def _int_to_base64url(n: int) -> str:
        """Конвертирует большое целое число (RSA modulus/exponent) в base64url без padding."""
        length = (n.bit_length() + 7) // 8  # минимальное число байт для хранения числа
        n_bytes = n.to_bytes(length, "big")
        return base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode()

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",   # ключ используется для подписи (не шифрования)
                "alg": "RS256",
                "n": _int_to_base64url(pub_numbers.n),  # модуль
                "e": _int_to_base64url(pub_numbers.e),  # публичная экспонента (обычно 65537)
            }
        ]
    }
