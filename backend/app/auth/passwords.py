"""Пароли: argon2id (параметры по умолчанию argon2-cffi, RFC 9106 low-memory)."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Проверка по этому хешу, когда пользователя нет: время ответа не выдаёт, есть ли email.
_DUMMY_HASH = _hasher.hash("dummy password for timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
