from __future__ import annotations
from cryptography.fernet import Fernet
from app.config import get_settings

# Синглтоны Fernet-объектов – инициализируются при первом вызове.
# Это безопасно, так как ключи не меняются в процессе работы сервиса.
_phone_fernet: Fernet | None = None
_totp_fernet: Fernet | None = None


def _get_phone_fernet() -> Fernet:
    """
    Возвращает Fernet-экземпляр для шифрования телефонов.

    Если переменная окружения ENCRYPT_KEY_PHONE не задана (например, при
    локальной разработке), генерируется случайный ключ. Это означает, что
    при перезапуске сервиса старые зашифрованные телефоны стать нечитаемыми.
    В production ключ обязан быть зафиксирован.
    """
    global _phone_fernet
    if _phone_fernet is None:
        settings = get_settings()
        key = settings.ENCRYPT_KEY_PHONE
        if not key or key in ("generate_me", ""):
            # Fallback для разработки – в production так делать нельзя
            key = Fernet.generate_key().decode()
        _phone_fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _phone_fernet


def _get_totp_fernet() -> Fernet:
    """
    Возвращает Fernet-экземпляр для шифрования TOTP-секретов.
    Использует отдельный ключ ENCRYPT_KEY_TOTP – компрометация одного ключа
    не раскрывает другой тип ПДн.
    """
    global _totp_fernet
    if _totp_fernet is None:
        settings = get_settings()
        key = settings.ENCRYPT_KEY_TOTP
        if not key or key in ("generate_me", ""):
            key = Fernet.generate_key().decode()
        _totp_fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _totp_fernet


def encrypt_phone(phone: str) -> str:
    """Шифрует номер телефона. Результат сохраняется в users.phone_encrypted."""
    return _get_phone_fernet().encrypt(phone.encode()).decode()


def decrypt_phone(encrypted: str) -> str:
    """Расшифровывает номер телефона. Вызывается только при запросе ПДн субъектом."""
    return _get_phone_fernet().decrypt(encrypted.encode()).decode()


def encrypt_totp(secret: str) -> str:
    """Шифрует TOTP base32-секрет. Результат сохраняется в totp_devices.secret_encrypted."""
    return _get_totp_fernet().encrypt(secret.encode()).decode()


def decrypt_totp(encrypted: str) -> str:
    """Расшифровывает TOTP-секрет для проверки кода при логине или подтверждении 2FA."""
    return _get_totp_fernet().decrypt(encrypted.encode()).decode()
