from collections.abc import AsyncIterator
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

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


async def get_current_user(session: SessionDep, settings: SettingsDep) -> User:
    """Текущий пользователь.

    До сессии 10 это всегда dev-пользователь из DEFAULT_USER_ID (создаётся миграцией).
    С появлением JWT меняется только эта функция — роуты зависят от CurrentUser.
    """
    user = await session.get(User, settings.default_user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
