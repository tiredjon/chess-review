"""Общие фикстуры.

Интеграционные тесты работают с отдельной БД (TEST_DATABASE_URL), которая
пересоздаётся с нуля и мигрируется в начале каждого прогона.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from app.core.config import Settings
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
    return Settings(
        app_env="test",
        database_url=integration_env.test_database_url,
        redis_url=integration_env.test_redis_url,
    )


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
def migrated_db(settings: Settings) -> str:
    """Чистая тестовая БД со схемой head. Синхронная: env.py сам вызывает asyncio.run."""
    asyncio.run(_recreate_database(settings.database_url))
    command.upgrade(alembic_config(settings.database_url), "head")
    return settings.database_url


@pytest.fixture
async def client(settings: Settings, migrated_db: str) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with (
        LifespanManager(app) as manager,
        AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as ac,
    ):
        yield ac
