import asyncio

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.db.base import Base
from tests.conftest import alembic_config

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "users",
    "games",
    "analyses",
    "moves",
    "explanations",
    "position_evals",
    "puzzles",
    "import_jobs",
    "puzzle_attempts",
    "refresh_tokens",
}


async def _table_names(url: str) -> set[str]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: inspect(c).get_table_names())
    finally:
        await engine.dispose()
    return set(names) - {"alembic_version"}


async def _schema_diff(url: str) -> list[object]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(
                lambda c: compare_metadata(
                    MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata
                )
            )
    finally:
        await engine.dispose()


def test_migrations_create_all_tables(migrated_db: str) -> None:
    assert asyncio.run(_table_names(migrated_db)) == EXPECTED_TABLES


def test_models_match_migrations(migrated_db: str) -> None:
    assert asyncio.run(_schema_diff(migrated_db)) == []


def test_downgrade_and_upgrade_roundtrip(migrated_db: str) -> None:
    cfg = alembic_config(migrated_db)

    command.downgrade(cfg, "base")
    assert asyncio.run(_table_names(migrated_db)) == set()

    command.upgrade(cfg, "head")
    assert asyncio.run(_table_names(migrated_db)) == EXPECTED_TABLES


def test_settings_fixture_points_to_test_db(settings: Settings) -> None:
    assert settings.database_url.endswith("_test")
