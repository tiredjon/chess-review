"""Клиент Lichess Opening Explorer: разбор живых ответов (tests/data/explorer), вежливость
(один запрос за раз, пауза между запросами), повторы 429 / 5xx / сети. Без сети и реальных sleep."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import chess
import httpx
import pytest

from app.explorer.client import LichessExplorer, parse_master_pgn
from app.explorer.types import ExplorerSource, ExplorerUnavailableError
from app.importers.http import RetryPolicy

DATA = Path(__file__).parent / "data" / "explorer"
AFTER_E4 = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")


def _json(name: str) -> dict[str, object]:
    data: dict[str, object] = json.loads((DATA / name).read_text())
    return data


class Clock:
    """Часы, которые двигает подменный sleep."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make(
    handler: Callable[[httpx.Request], httpx.Response], clock: Clock, *, interval: float = 1.0
) -> LichessExplorer:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    policy = RetryPolicy(attempts=3, rate_limit_wait_s=60, backoff_s=1, sleep=clock.sleep)
    return LichessExplorer(
        http, base_url="https://explorer.test/", min_interval_s=interval, policy=policy, clock=clock
    )


async def test_masters_parsed_from_live_response() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_json("masters_e4.json"))

    explorer = make(handler, Clock())
    position = await explorer.position(AFTER_E4)

    request = seen[0]
    assert request.url.path == "/masters"
    assert request.url.params["fen"] == AFTER_E4.fen()
    assert request.url.params["moves"] == "12"
    assert request.url.params["topGames"] == "4"
    assert position.source is ExplorerSource.MASTERS
    assert position.games == position.white + position.draws + position.black > 1000
    first = position.moves[0]
    assert (first.uci, first.san) == ("c7c5", "c5")
    assert first.games == 194269 + 273851 + 159166
    assert first.average_rating == 2396
    assert [m.games for m in position.moves] == sorted(
        (m.games for m in position.moves), reverse=True
    )
    ref = position.top_games[0]
    assert (ref.id, ref.white, ref.black, ref.white_rating, ref.black_rating) == (
        "zEaZZlau",
        "Nakamura, Hi",
        "Carlsen, M.",
        2816,
        2839,
    )
    assert (ref.winner, ref.year, ref.uci) == ("black", 2025, "d7d6")
    assert (position.opening_eco, position.opening_name) == ("B00", "King's Pawn Game")


async def test_lichess_params_and_no_top_games() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_json("lichess_e4.json"))

    position = await make(handler, Clock()).position(AFTER_E4, source=ExplorerSource.LICHESS)

    params = seen[0].url.params
    assert seen[0].url.path == "/lichess"
    assert params["variant"] == "standard"
    assert params["speeds"] == "blitz,rapid,classical"
    assert params["ratings"] == "2000,2200,2500"
    assert (params["topGames"], params["recentGames"]) == ("0", "0")
    assert position.source is ExplorerSource.LICHESS
    assert position.top_games == ()
    assert position.moves[0].san == "c5"


async def test_master_game_headers_from_pgn() -> None:
    pgn = (DATA / "master_game.pgn").read_text()
    game = await make(lambda r: httpx.Response(200, text=pgn), Clock()).master_game("zEaZZlau")

    assert (game.white, game.black) == ("Nakamura, Hi", "Carlsen, M.")
    assert (game.white_rating, game.black_rating, game.year, game.result) == (
        2816,
        2839,
        2025,
        "0-1",
    )
    assert game.pgn.startswith("[Event")
    assert "1. e4 d6" in game.pgn


def test_pgn_without_headers_gets_defaults() -> None:
    game = parse_master_pgn("abcd1234", "1. e4 e5 *")
    assert (game.white, game.white_rating, game.year, game.result) == ("?", None, None, "*")


async def test_pause_between_requests() -> None:
    clock = Clock()
    explorer = make(lambda r: httpx.Response(200, json=_json("masters_e4.json")), clock)

    await explorer.position(AFTER_E4)
    assert clock.sleeps == []  # первый запрос — без паузы
    clock.now += 0.25
    await explorer.position(AFTER_E4)
    assert clock.sleeps == [pytest.approx(0.75)]
    clock.now += 5
    await explorer.position(AFTER_E4)
    assert len(clock.sleeps) == 1  # пауза уже прошла сама


async def test_one_request_at_a_time() -> None:
    active = 0
    peak = 0
    clock = Clock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json=_json("masters_e4.json"))

    explorer = make(handler, clock)  # type: ignore[arg-type]
    await asyncio.gather(*(explorer.position(AFTER_E4) for _ in range(4)))

    assert peak == 1
    assert len(clock.sleeps) == 3


async def test_429_waits_and_repeats() -> None:
    clock = Clock()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=_json("masters_e4.json"))

    position = await make(handler, clock).position(AFTER_E4)

    assert calls == 2
    assert position.games > 0
    assert clock.sleeps == [60]


async def test_5xx_retries_with_backoff_then_unavailable() -> None:
    clock = Clock()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    with pytest.raises(ExplorerUnavailableError):
        await make(handler, clock).position(AFTER_E4)

    assert calls == 3
    assert clock.sleeps == [1, 2]


async def test_network_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("нет сети")

    with pytest.raises(ExplorerUnavailableError):
        await make(handler, Clock()).master_game("abcd1234")


@pytest.mark.parametrize("status", [401, 404])
async def test_other_statuses_are_unavailable(status: int) -> None:
    # Lichess без токена отвечает 401 на базу `lichess`; нет партии — 404.
    clock = Clock()
    with pytest.raises(ExplorerUnavailableError, match=str(status)):
        await make(lambda r: httpx.Response(status), clock).position(
            AFTER_E4, source=ExplorerSource.LICHESS
        )
    assert clock.sleeps == []


async def test_garbage_json_is_unavailable() -> None:
    with pytest.raises(ExplorerUnavailableError):
        await make(lambda r: httpx.Response(200, json={"oops": 1}), Clock()).position(AFTER_E4)


async def test_request_after_failure_still_paused() -> None:
    clock = Clock()
    responses = iter([httpx.Response(404), httpx.Response(200, json=_json("masters_e4.json"))])
    explorer = make(lambda r: next(responses), clock)

    with pytest.raises(ExplorerUnavailableError):
        await explorer.position(AFTER_E4)
    await explorer.position(AFTER_E4)

    assert clock.sleeps == [1.0]
