"""Клиент Lichess tablebase (вежливость, повторы, ошибки) и кэш в БД. Без сети и реальных sleep."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import chess
import httpx
import pytest
from sqlalchemy import delete, select

from app.db.models import TablebaseCacheEntry
from app.db.session import Database
from app.endgames.tablebase import CachedTablebase, LichessTablebase, TablebaseUnavailableError
from app.importers.http import RetryPolicy
from tests.endgame_fakes import FakeRawTablebase, fixture_answers

LUCENA = "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1"
MATE_R = chess.Board("8/8/8/4k3/8/8/8/R3K3 w - - 12 40")


class Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make(
    handler: Callable[[httpx.Request], httpx.Response], clock: Clock, *, interval: float = 0.5
) -> LichessTablebase:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), headers={"User-Agent": "ChessReview/test"}
    )
    policy = RetryPolicy(attempts=3, rate_limit_wait_s=60, backoff_s=1, sleep=clock.sleep)
    return LichessTablebase(
        http, base_url="https://tb.test/", min_interval_s=interval, policy=policy, clock=clock
    )


async def test_request_and_parse() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=fixture_answers()[LUCENA])

    position = await make(handler, Clock()).probe(chess.Board(LUCENA))

    assert seen[0].url.path == "/standard"
    assert seen[0].url.params["fen"] == LUCENA
    assert seen[0].headers["User-Agent"] == "ChessReview/test"
    assert position.category == "win"
    assert position.moves[0].san == "Rd1+"


async def test_clocks_are_not_sent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.params["fen"])
        return httpx.Response(200, json={"category": "win", "moves": []})

    await make(handler, Clock()).probe(MATE_R)
    assert seen == ["8/8/8/4k3/8/8/8/R3K3 w - - 0 1"]


async def test_pause_between_requests() -> None:
    clock = Clock()

    def handler(request: httpx.Request) -> httpx.Response:
        clock.now += 0.1  # запрос занял 0,1 с
        return httpx.Response(200, json={"category": "draw", "moves": []})

    tablebase = make(handler, clock, interval=0.5)
    await tablebase.probe(MATE_R)
    await tablebase.probe(MATE_R)
    await tablebase.probe(MATE_R)
    assert clock.sleeps == [pytest.approx(0.5), pytest.approx(0.5)]


async def test_one_request_at_a_time() -> None:
    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json={"category": "draw", "moves": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    policy = RetryPolicy(attempts=1, sleep=Clock().sleep)
    tablebase = LichessTablebase(http, base_url="https://tb.test", min_interval_s=0, policy=policy)
    await asyncio.gather(*(tablebase.probe(MATE_R) for _ in range(4)))
    assert peak == 1


async def test_429_waits_and_retries() -> None:
    clock = Clock()
    answers = iter(
        [
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(429),
            httpx.Response(200, json={"category": "win", "moves": []}),
        ]
    )
    position = await make(lambda _: next(answers), clock).probe(MATE_R)
    assert position.category == "win"
    assert clock.sleeps == [7, 60]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(400, text="bad fen"),
        httpx.Response(200, text="<html>"),
        httpx.Response(200, json=["x"]),
    ],
    ids=["5xx", "4xx", "not-json", "shape"],
)
async def test_unavailable(response: httpx.Response) -> None:
    with pytest.raises(TablebaseUnavailableError):
        await make(lambda _: response, Clock()).probe(MATE_R)


async def test_network_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("нет сети")

    with pytest.raises(TablebaseUnavailableError):
        await make(handler, Clock()).probe(MATE_R)


@pytest.fixture
async def tdb(db: Database) -> Database:
    async with db.sessionmaker() as session:
        await session.execute(delete(TablebaseCacheEntry))
        await session.commit()
    return db


@pytest.mark.integration
async def test_cache_hits_db(tdb: Database) -> None:
    inner = FakeRawTablebase()
    cached = CachedTablebase(inner, tdb, now=lambda: datetime(2026, 11, 1, tzinfo=UTC))
    board = chess.Board(LUCENA)

    first = await cached.probe(board)
    # Те же фигуры с другими счётчиками — та же запись.
    second = await cached.probe(chess.Board(LUCENA.replace(" 0 1", " 9 70")))

    assert inner.calls == [board.epd()]
    assert first == second
    async with tdb.sessionmaker() as session:
        rows = (await session.execute(select(TablebaseCacheEntry))).scalars().all()
    assert [row.epd for row in rows] == [board.epd()]
    assert rows[0].data == fixture_answers()[LUCENA]


@pytest.mark.integration
async def test_cache_does_not_store_failures(tdb: Database) -> None:
    inner = FakeRawTablebase(fail=True)
    cached = CachedTablebase(inner, tdb)
    with pytest.raises(TablebaseUnavailableError):
        await cached.probe(chess.Board(LUCENA))
    async with tdb.sessionmaker() as session:
        assert (await session.execute(select(TablebaseCacheEntry))).first() is None
