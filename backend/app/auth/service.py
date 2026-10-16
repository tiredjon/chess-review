"""Регистрация, вход, обновление и отзыв refresh-токенов.

Refresh-токены одного входа — цепочка (`family_id`). Обновление помечает предъявленный
токен заменённым и выдаёт следующий. Повтор заменённого токена позже
`REFRESH_REUSE_GRACE_S` — признак кражи: отзывается вся цепочка. В пределах окна
(две вкладки обновились одновременно) — отказ без отзыва, клиент повторяет запрос
с уже новым cookie.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.tokens import hash_refresh_token, new_refresh_token
from app.core.config import Settings
from app.core.errors import ErrorCode
from app.db.models import RefreshToken, User


class AuthError(Exception):
    def __init__(self, code: ErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class Session:
    user: User
    refresh_token: str


def _now() -> datetime:
    return datetime.now(UTC)


async def _issue_refresh(
    session: AsyncSession, settings: Settings, user_id: uuid.UUID, family_id: uuid.UUID
) -> str:
    token = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            family_id=family_id,
            expires_at=_now() + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    return token


async def _start_session(session: AsyncSession, settings: Settings, user: User) -> Session:
    # Заодно убрать истёкшие токены пользователя, чтобы таблица не росла.
    await session.execute(
        delete(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.expires_at < _now()
        )
    )
    token = await _issue_refresh(session, settings, user.id, uuid.uuid4())
    await session.commit()
    return Session(user=user, refresh_token=token)


async def register(
    session: AsyncSession, settings: Settings, email: str, password: str, lang: str | None
) -> Session:
    """Новый пользователь. Первый зарегистрированный получает запись dev-пользователя
    (с его партиями, анализами и пазлами), если `AUTH_CLAIM_DEV_USER`."""
    email = email.strip().lower()
    taken = await session.scalar(select(User.id).where(func.lower(User.email) == email))
    if taken is not None:
        raise AuthError(ErrorCode.EMAIL_TAKEN)
    user = None
    if settings.auth_claim_dev_user:
        user = await session.scalar(
            select(User)
            .where(User.id == settings.default_user_id, User.password_hash.is_(None))
            .with_for_update()
        )
    if user is None:
        user = User(email=email)
        session.add(user)
    user.email = email
    user.password_hash = hash_password(password)
    if lang is not None:
        user.lang = lang
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AuthError(ErrorCode.EMAIL_TAKEN) from exc
    return await _start_session(session, settings, user)


async def login(session: AsyncSession, settings: Settings, email: str, password: str) -> Session:
    user = await session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if not verify_password(user.password_hash if user else None, password):
        raise AuthError(ErrorCode.INVALID_CREDENTIALS)
    assert user is not None
    assert user.password_hash is not None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return await _start_session(session, settings, user)


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def refresh(session: AsyncSession, settings: Settings, token: str) -> Session:
    """Следующий токен цепочки взамен предъявленного."""
    row = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(token))
        .with_for_update()
    )
    now = _now()
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise AuthError(ErrorCode.REFRESH_INVALID)
    if row.replaced_at is not None:
        if now - row.replaced_at <= timedelta(seconds=settings.refresh_reuse_grace_s):
            await session.rollback()
            raise AuthError(ErrorCode.REFRESH_ROTATED)
        await _revoke_family(session, row.family_id)
        await session.commit()
        raise AuthError(ErrorCode.REFRESH_INVALID)
    user = await session.get(User, row.user_id)
    if user is None:  # pragma: no cover — каскад удаляет токены вместе с пользователем
        raise AuthError(ErrorCode.REFRESH_INVALID)
    row.replaced_at = now
    new_token = await _issue_refresh(session, settings, row.user_id, row.family_id)
    await session.commit()
    return Session(user=user, refresh_token=new_token)


async def logout(session: AsyncSession, token: str) -> None:
    """Отзыв всей цепочки предъявленного токена (выход на этом устройстве)."""
    family_id = await session.scalar(
        select(RefreshToken.family_id).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if family_id is not None:
        await _revoke_family(session, family_id)
        await session.commit()
