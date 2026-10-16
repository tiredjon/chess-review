"""Токены: access (JWT, короткий, в памяти браузера), stream (JWT для SSE одного
анализа) и refresh (случайная строка в httpOnly-cookie, в БД — её sha256)."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

from app.core.config import Settings

ALGORITHM = "HS256"
TokenType = Literal["access", "stream"]


class TokenError(Exception):
    def __init__(self, *, expired: bool = False) -> None:
        super().__init__("expired" if expired else "invalid")
        self.expired = expired


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: uuid.UUID
    # Только у stream: анализ, события которого можно читать.
    analysis_id: uuid.UUID | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def create_token(
    settings: Settings,
    user_id: uuid.UUID,
    token_type: TokenType = "access",
    *,
    analysis_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> str:
    now = now or _now()
    ttl = settings.access_token_ttl_s if token_type == "access" else settings.stream_token_ttl_s
    payload: dict[str, object] = {
        "sub": str(user_id),
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    if analysis_id is not None:
        payload["aid"] = str(analysis_id)
    return jwt.encode(payload, settings.jwt_key, algorithm=ALGORITHM)


def decode_token(settings: Settings, token: str, token_type: TokenType = "access") -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_key,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError(expired=True) from exc
    except jwt.PyJWTError as exc:
        raise TokenError from exc
    if payload.get("typ") != token_type:
        raise TokenError
    try:
        user_id = uuid.UUID(payload["sub"])
        aid = payload.get("aid")
        analysis_id = uuid.UUID(aid) if aid is not None else None
    except (ValueError, TypeError, AttributeError) as exc:
        raise TokenError from exc
    if token_type == "stream" and analysis_id is None:
        raise TokenError
    return TokenClaims(user_id=user_id, analysis_id=analysis_id)


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
