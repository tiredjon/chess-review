import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError, ErrorCode
from app.auth.tokens import TokenError, decode_token
from app.core.config import Settings
from app.db.models import User
from app.db.session import Database
from app.explain.llm import LLMProvider
from app.explain.service import Explainer


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis


def get_arq(request: Request) -> ArqRedis:
    arq: ArqRedis = request.app.state.redis
    return arq


def get_explainer(request: Request) -> Explainer:
    llm: LLMProvider | None = request.app.state.llm
    return Explainer(
        llm,
        get_db(request).sessionmaker,
        concurrency=get_settings(request).llm_max_concurrency,
    )


SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[Database, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
ArqDep = Annotated[ArqRedis, Depends(get_arq)]
ExplainerDep = Annotated[Explainer, Depends(get_explainer)]


async def get_session(db: DatabaseDep) -> AsyncIterator[AsyncSession]:
    async with db.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


_bearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _unauthorized(code: ErrorCode, message: str) -> ApiError:
    return ApiError(
        status.HTTP_401_UNAUTHORIZED, code, message, headers={"WWW-Authenticate": "Bearer"}
    )


def token_error(exc: TokenError) -> ApiError:
    if exc.expired:
        return _unauthorized(ErrorCode.TOKEN_EXPIRED, "Токен истёк")
    return _unauthorized(ErrorCode.TOKEN_INVALID, "Некорректный токен")


async def load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise _unauthorized(ErrorCode.TOKEN_INVALID, "Пользователь не найден")
    return user


async def get_current_user(
    session: SessionDep, settings: SettingsDep, credentials: BearerDep
) -> User:
    """Текущий пользователь по access-токену (`Authorization: Bearer <JWT>`).

    Все роуты получают пользователя только отсюда (через CurrentUser).
    """
    if credentials is None:
        raise _unauthorized(ErrorCode.NOT_AUTHENTICATED, "Нужен вход")
    try:
        claims = decode_token(settings, credentials.credentials)
    except TokenError as exc:
        raise token_error(exc) from exc
    return await load_user(session, claims.user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]
