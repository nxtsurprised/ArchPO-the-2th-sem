from __future__ import annotations
import re
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.config import get_settings


def _get_hasher() -> PasswordHasher:
    """
    Создаёт PasswordHasher с параметрами из конфига.
    Argon2id – рекомендация OWASP и NIST для хранения паролей:
      - time_cost=3  – число итераций
      - memory_cost=65536 – 64 МБ памяти на хеш (защита от GPU-атак)
    """
    settings = get_settings()
    return PasswordHasher(
        time_cost=settings.ARGON2_TIME_COST,
        memory_cost=settings.ARGON2_MEMORY_COST,
    )


def hash_password(password: str) -> str:
    """Возвращает Argon2id-хеш пароля для сохранения в БД."""
    return _get_hasher().hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """
    Проверяет пароль против сохранённого хеша.

    Специальный случай "DEACTIVATED" – маркер обезличенного аккаунта,
    вход для таких аккаунтов заблокирован на уровне логики без обращения к Argon2.
    """
    if hashed == "DEACTIVATED":
        return False
    try:
        return _get_hasher().verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_policy(
    password: str,
    user_email: str = "",
    user_fullname: str = "",
) -> list[str]:
    """
    Проверяет пароль на соответствие политике безопасности.
    Возвращает список нарушений (пустой список = пароль валиден).

    Политика:
      1. Минимальная длина (из конфига, по умолчанию 12 символов).
      2. Не менее 3 из 4 категорий: заглавные, строчные, цифры, спецсимволы.
      3. Пароль не должен содержать логин пользователя (левая часть email).
      4. Пароль не должен содержать части ФИО длиннее 3 символов.
      5. Запрещены слова: система, system, gost, гост.
    """
    settings = get_settings()
    errors: list[str] = []

    # Проверка 1 – длина
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Пароль должен содержать не менее {settings.PASSWORD_MIN_LENGTH} символов")

    # Проверка 2 – категории символов
    categories = 0
    if re.search(r"[A-ZА-ЯЁ]", password):
        categories += 1  # заглавные латиница / кириллица
    if re.search(r"[a-zа-яё]", password):
        categories += 1  # строчные латиница / кириллица
    if re.search(r"\d", password):
        categories += 1  # цифры
    if re.search(r"[!@#$%^&*()\-_=+\[\]{};':\"\\|,.<>/?~`]", password):
        categories += 1  # спецсимволы

    if categories < 3:
        errors.append("Пароль должен содержать символы из не менее 3 категорий: заглавные, строчные, цифры, спецсимволы")

    # Проверка 3 – логин не должен быть подстрокой пароля (проверяем local-часть email)
    forbidden_substrings = ["система", "system", "gost", "гост"]
    if user_email:
        local = user_email.split("@")[0].lower()
        if len(local) >= 4 and local in password.lower():
            errors.append("Пароль не должен содержать логин")

    # Проверка 4 – части ФИО (только слова длиннее 3 символов, чтобы не блокировать "Ли", "Ян")
    if user_fullname:
        for part in user_fullname.lower().split():
            if len(part) >= 4 and part in password.lower():
                errors.append("Пароль не должен содержать части ФИО")
                break  # достаточно одного нарушения

    # Проверка 5 – запрещённые слова
    for f in forbidden_substrings:
        if f in password.lower():
            errors.append(f"Пароль не должен содержать запрещённую строку: {f}")

    return errors
