"""Кэш Explorer в БД: попадание, промах, истёкший TTL, источники, PGN мастеров навсегда."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import chess
import pytest
from sqlalchemy import func, select, text

from app.db.models import ExplorerCacheEntry, MasterGame
from app.db.session import Database
from app.explorer.cache import CachedExplorer, position_from_data, position_to_data
from app.explorer.types import ExplorerSource, ExplorerUnavailableError
from tests.explorer_fakes import FakeExplorer

AFTER_E4 = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
# Та же позиция, другие счётчики ходов: ключ — EPD, кэш общий.
AFTER_E4_LATER = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 5 9")


class Now:
    def __init__(self) -> None:
        self.value = datetime(2026, 11, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
async def clean(db: Database) -> AsyncIterator[Database]:
    async with db.engine.begin() as conn:
        await conn.execute(text("DELETE FROM explorer_cache"))
        await conn.execute(text("DELETE FROM master_games"))
    return db  # type: ignore[return-value]


def make(db: Database, inner: FakeExplorer, now: Now, ttl: int = 30) -> CachedExplorer:
    return CachedExplorer(inner, db, ttl_days=ttl, now=now)


async def rows(db: Database) -> int:
    async with db.sessionmaker() as session:
        return int(await session.scalar(select(func.count()).select_from(ExplorerCacheEntry)) or 0)


async def test_miss_then_hit(clean: Database) -> None:
    inner, now = FakeExplorer(), Now()
    explorer = make(clean, inner, now)

    first = await explorer.position(AFTER_E4)
    now.value += timedelta(days=29)
    second = await explorer.position(AFTER_E4_LATER)

    assert second == first
    assert len(inner.position_calls) == 1
    assert await rows(clean) == 1


async def test_expired_ttl_refetches_and_updates(clean: Database) -> None:
    inner, now = FakeExplorer(), Now()
    explorer = make(clean, inner, now, ttl=30)

    await explorer.position(AFTER_E4)
    now.value += timedelta(days=31)
    await explorer.position(AFTER_E4)

    assert len(inner.position_calls) == 2
    assert await rows(clean) == 1
    async with clean.sessionmaker() as session:
        row = (await session.scalars(select(ExplorerCacheEntry))).one()
        assert row.fetched_at == now.value


async def test_sources_cached_separately(clean: Database) -> None:
    inner = FakeExplorer()
    explorer = make(clean, inner, Now())

    masters = await explorer.position(AFTER_E4, source=ExplorerSource.MASTERS)
    lichess = await explorer.position(AFTER_E4, source=ExplorerSource.LICHESS)
    await explorer.position(AFTER_E4, source=ExplorerSource.LICHESS)

    assert masters.top_games
    assert not lichess.top_games
    assert lichess.source is ExplorerSource.LICHESS
    assert [s for _, s in inner.position_calls] == [ExplorerSource.MASTERS, ExplorerSource.LICHESS]
    async with clean.sessionmaker() as session:
        keys = {
            (r.source, r.params) for r in (await session.scalars(select(ExplorerCacheEntry))).all()
        }
    assert keys == {("masters", ""), ("lichess", "blitz,rapid,classical|2000,2200,2500")}


async def test_failure_not_cached(clean: Database) -> None:
    inner = FakeExplorer(fail=True)
    explorer = make(clean, inner, Now())

    with pytest.raises(ExplorerUnavailableError):
        await explorer.position(AFTER_E4)

    assert await rows(clean) == 0


async def test_purge_expired(clean: Database) -> None:
    inner, now = FakeExplorer(), Now()
    explorer = make(clean, inner, now)
    await explorer.position(AFTER_E4)
    now.value += timedelta(days=31)

    assert await explorer.purge_expired() == 1
    assert await rows(clean) == 0


async def test_master_game_cached_forever(clean: Database) -> None:
    inner, now = FakeExplorer(), Now()
    explorer = make(clean, inner, now)

    first = await explorer.master_game("zEaZZlau")
    now.value += timedelta(days=3650)
    second = await explorer.master_game("zEaZZlau")

    assert second == first
    assert inner.game_calls == ["zEaZZlau"]
    async with clean.sessionmaker() as session:
        row = await session.get(MasterGame, "zEaZZlau")
        assert row is not None
        assert (row.white, row.black, row.white_rating, row.year, row.result) == (
            "Nakamura, Hi",
            "Carlsen, M.",
            2816,
            2025,
            "0-1",
        )


async def test_data_roundtrip() -> None:
    position = await FakeExplorer().position(AFTER_E4)
    assert position_from_data(position_to_data(position)) == position
