"""Общие фикстуры.

Интеграционные тесты работают с отдельной БД (TEST_DATABASE_URL), которая
пересоздаётся с нуля и мигрируется в начале каждого прогона.
"""

import asyncio
import os
import shutil
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.auth.tokens import create_token
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parent.parent


class IntegrationEnv(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    test_database_url: str = "postgresql+asyncpg://chess:chess@localhost:5432/chess_review_test"
    test_redis_url: str = "redis://localhost:6379/15"


@pytest.fixture(scope="session")
def integration_env() -> IntegrationEnv:
    return IntegrationEnv()


@pytest.fixture(scope="session")
def settings(integration_env: IntegrationEnv) -> Settings:
    # Лимиты и «первый зарегистрированный получает dev-пользователя» включаются в своих
    # тестах (test_ratelimit.py, test_api_auth.py), иначе тесты влияли бы друг на друга.
    return Settings(
        app_env="test",
        database_url=integration_env.test_database_url,
        redis_url=integration_env.test_redis_url,
        rate_limit_enabled=False,
        auth_claim_dev_user=False,
    )


def auth_headers(settings: Settings, user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(settings, user_id)}"}


@asynccontextmanager
async def api_client(
    settings: Settings,
    user_id: uuid.UUID | None = None,
    *,
    setup: Callable[[FastAPI], None] | None = None,
    anonymous: bool = False,
) -> AsyncIterator[AsyncClient]:
    """Клиент API от имени пользователя (по умолчанию — dev-пользователь из миграции).
    `setup(app)` вызывается после старта приложения (подмена зависимостей, LLM)."""
    app = create_app(settings)
    headers = {} if anonymous else auth_headers(settings, user_id or settings.default_user_id)
    async with LifespanManager(app) as manager:
        if setup is not None:
            setup(app)
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
            yield ac


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.attributes["skip_logging_config"] = True
    return cfg


async def _recreate_database(database_url: str) -> None:
    url = make_url(database_url)
    if not url.database or not url.database.endswith("_test"):
        raise RuntimeError(f"Отказ пересоздавать БД без суффикса _test: {url.database!r}")
    conn = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port or 5432,
        database="postgres",
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def stockfish_path(settings: Settings) -> str:
    """Путь к Stockfish. В Docker-образе (REQUIRE_STOCKFISH=1) движок обязан быть."""
    path = shutil.which(settings.stockfish_path)
    if path is None:
        if os.environ.get("REQUIRE_STOCKFISH") == "1":
            pytest.fail(f"Stockfish не найден: {settings.stockfish_path}")
        pytest.skip("Stockfish не установлен локально (brew install stockfish)")
    return path


@pytest.fixture(scope="session")
def migrated_db(settings: Settings) -> str:
    """Чистая тестовая БД со схемой head. Синхронная: env.py сам вызывает asyncio.run."""
    asyncio.run(_recreate_database(settings.database_url))
    command.upgrade(alembic_config(settings.database_url), "head")
    return settings.database_url


@pytest.fixture
async def client(settings: Settings, migrated_db: str) -> AsyncIterator[AsyncClient]:
    """Клиент API от имени dev-пользователя."""
    async with api_client(settings) as ac:
        yield ac


@pytest.fixture
async def db(migrated_db: str) -> AsyncIterator[Database]:
    """Тестовая БД без партий, пазлов и кэша оценок (пользователи из миграции остаются)."""
    database = Database(migrated_db)
    async with database.engine.begin() as conn:
        await conn.execute(text("DELETE FROM puzzles"))
        await conn.execute(text("DELETE FROM games"))
        await conn.execute(text("DELETE FROM position_evals"))
    yield database
    await database.dispose()


@pytest.fixture
async def redis(settings: Settings) -> AsyncIterator[Redis]:
    """Пустая тестовая база Redis."""
    client = Redis.from_url(settings.redis_url)
    await client.flushdb()
    yield client
    await client.aclose()
