"""Клиенты Lichess / Chess.com, повторы HTTP и разбор полученных партий (без сети)."""

import re
from datetime import date

import httpx
import pytest

from app.core.config import Settings
from app.db.models import Color
from app.importers.chesscom import ChessComClient
from app.importers.http import (
    RetryPolicy,
    SourceError,
    UserNotFoundError,
    get_with_retry,
    make_http_client,
)
from app.importers.lichess import LichessClient
from app.importers.sources import SourceGame, convert, convert_page
from app.importers.types import ImportedGame
from tests.import_fakes import FAST_RETRY, FakeChessCom, FakeLichess, make_pgn, mock_client

# --- HTTP: повторы ---


class Script:
    """Отвечает по списку; исключение в списке — сетевая ошибка."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def test_retry_honours_retry_after_then_succeeds() -> None:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    script = Script(
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(429),
        httpx.Response(200, text="ok"),
    )
    policy = RetryPolicy(attempts=3, rate_limit_wait_s=60, backoff_s=1, sleep=sleep)
    async with mock_client(script) as http:
        response = await get_with_retry(http, "https://x.test/a", source="X", policy=policy)

    assert response.text == "ok"
    assert waits == [7.0, 60.0]


async def test_retry_backs_off_on_server_and_network_errors() -> None:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    script = Script(httpx.ConnectError("down"), httpx.Response(503), httpx.Response(404))
    policy = RetryPolicy(attempts=3, backoff_s=1, sleep=sleep)
    async with mock_client(script) as http:
        response = await get_with_retry(http, "https://x.test/a", source="X", policy=policy)

    # 404 — не повод повторять: его разбирает клиент источника.
    assert response.status_code == 404
    assert waits == [1.0, 2.0]


@pytest.mark.parametrize(
    ("final", "message"),
    [
        (httpx.Response(500), "X: ошибка сервера 500"),
        (httpx.Response(429), "X: превышен лимит запросов"),
        (httpx.ReadTimeout("slow"), "X недоступен (ReadTimeout)"),
    ],
)
async def test_retry_gives_up_after_attempts(
    final: httpx.Response | Exception, message: str
) -> None:
    script = Script(httpx.Response(502), final)
    policy = RetryPolicy(attempts=2, rate_limit_wait_s=0, backoff_s=0, sleep=FAST_RETRY.sleep)
    async with mock_client(script) as http:
        with pytest.raises(SourceError, match=re.escape(message)):
            await get_with_retry(http, "https://x.test/a", source="X", policy=policy)
    assert script.calls == 2


def test_http_client_sends_own_user_agent() -> None:
    settings = Settings(import_user_agent="ChessReview/test", import_http_timeout_s=5)
    http = make_http_client(settings)

    # Lichess отвечает 404 на дефолтный UA httpx — он не должен уходить.
    assert http.headers["User-Agent"] == "ChessReview/test"
    assert http.timeout.read == 5
    assert RetryPolicy.from_settings(settings).attempts == settings.import_max_attempts


# --- Lichess ---


async def collect_lichess(
    fake: FakeLichess,
    username: str,
    max_games: int,
    *,
    page_size: int = 100,
    token: str | None = None,
) -> list[list[SourceGame]]:
    async with mock_client(fake) as http:
        client = LichessClient(
            http,
            base_url="https://lichess.test/",
            token=token,
            policy=FAST_RETRY,
            page_size=page_size,
        )
        return [page async for page in client.games(username, max_games)]


async def test_lichess_pages_with_until_up_to_max() -> None:
    fake = FakeLichess()
    fake.add_games("Alice", 25)

    pages = await collect_lichess(fake, "alice", 12, page_size=5)

    assert [len(page) for page in pages] == [5, 5, 2]
    ids = [game.external_id for page in pages for game in page]
    assert ids == [g["id"] for g in fake.users["alice"][:12]]
    first, second, third = (request.url.params for request in fake.requests)
    assert "until" not in first
    assert first["max"] == "5"
    assert first["pgnInJson"] == "true"
    assert "bullet" in first["perfType"]
    assert "chess960" not in first["perfType"]
    assert int(second["until"]) == fake.users["alice"][4]["createdAt"] + 1
    # Самая старая партия прошлой страницы придёт повторно — её добираем сверх страницы.
    assert second["max"] == "6"
    assert third["max"] == "3"
    assert fake.requests[0].headers["Accept"] == "application/x-ndjson"
    assert "Authorization" not in fake.requests[0].headers
    assert fake.requests[0].url.host == "lichess.test"


async def test_lichess_stops_when_history_ends() -> None:
    fake = FakeLichess()
    fake.add_games("bob", 7)

    pages = await collect_lichess(fake, "bob", 100, page_size=5)

    assert [len(page) for page in pages] == [5, 2]
    assert len(fake.requests) == 2


async def test_lichess_keeps_games_with_same_time_on_page_border() -> None:
    fake = FakeLichess()
    fake.add_games("carol", 7)
    games = fake.users["carol"]
    # Партии 2–3 созданы в одну миллисекунду и попадают на стык страниц.
    games[3]["createdAt"] = games[2]["createdAt"]

    pages = await collect_lichess(fake, "carol", 6, page_size=3)

    ids = [game.external_id for page in pages for game in page]
    assert ids == [g["id"] for g in games[:6]]
    second = fake.requests[1].url.params
    assert int(second["until"]) == games[2]["createdAt"] + 1
    # Страница плюс одна партия, которая придёт повторно.
    assert second["max"] == "4"


async def test_lichess_sends_token_and_marks_variants() -> None:
    fake = FakeLichess()
    fake.add_games("dave", 2)
    fake.users["dave"][1]["variant"] = "chess960"

    (page,) = await collect_lichess(fake, "dave", 2, token="lip_secret")

    assert [game.standard for game in page] == [True, False]
    assert fake.requests[0].headers["Authorization"] == "Bearer lip_secret"


async def test_lichess_user_not_found() -> None:
    with pytest.raises(UserNotFoundError, match="nobody не найден на Lichess"):
        await collect_lichess(FakeLichess(), "nobody", 5)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401), "Lichess: ответ 401"),
        (httpx.Response(200, text="<html>"), "некорректный ответ"),
        (httpx.Response(200, text='{"variant": "standard"}\n'), "некорректный ответ"),
    ],
)
async def test_lichess_bad_responses(response: httpx.Response, message: str) -> None:
    fake = FakeLichess(failures=[response])
    fake.add_games("erin", 1)

    with pytest.raises(SourceError, match=message):
        await collect_lichess(fake, "erin", 5)


async def test_lichess_retries_rate_limit() -> None:
    fake = FakeLichess(failures=[httpx.Response(429)])
    fake.add_games("frank", 2)

    (page,) = await collect_lichess(fake, "frank", 5)

    assert len(page) == 2
    assert len(fake.requests) == 2


# --- Chess.com ---


async def collect_chesscom(
    fake: FakeChessCom, username: str, months: int, today: date
) -> list[list[SourceGame]]:
    async with mock_client(fake) as http:
        client = ChessComClient(http, base_url=fake.base + "/", policy=FAST_RETRY)
        return [page async for page in client.games(username, months, today=today)]


async def test_chesscom_takes_calendar_months_newest_first() -> None:
    fake = FakeChessCom()
    for year, month, game_id in [
        (2025, 11, 1),  # вне окна
        (2025, 12, 2),
        (2026, 2, 3),
        (2026, 2, 4),
    ]:
        fake.add_game("Gina", year, month, game_id)

    pages = await collect_chesscom(fake, "Gina", 3, today=date(2026, 2, 15))

    # Окно: декабрь, январь (пусто — архива нет), февраль.
    assert [[game.external_id for game in page] for page in pages] == [
        ["live/4", "live/3"],
        ["live/2"],
    ]
    paths = [request.url.path for request in fake.requests]
    assert paths == [
        "/pub/player/gina/games/archives",
        "/pub/player/gina/games/2026/02",
        "/pub/player/gina/games/2025/12",
    ]


async def test_chesscom_ids_and_variants() -> None:
    fake = FakeChessCom()
    fake.add_game("hal", 2026, 1, 10)
    fake.add_game("hal", 2026, 1, 11, rules="chess960")
    games = fake.users["hal"][(2026, 1)]
    games.append({**games[0], "url": "https://www.chess.com/game/daily/77", "end_time": 1})
    games.append({**games[0], "url": "", "uuid": "abc-def", "end_time": 0})
    games.append({**games[0], "url": "", "uuid": None, "end_time": 0})
    games.append("garbage")  # type: ignore[arg-type]

    (page,) = await collect_chesscom(fake, "hal", 1, today=date(2026, 1, 31))

    assert [(game.external_id, game.standard) for game in page] == [
        ("live/11", False),
        ("live/10", True),
        ("daily/77", True),
        ("abc-def", True),
    ]


async def test_chesscom_user_not_found_and_errors() -> None:
    with pytest.raises(UserNotFoundError, match=r"ivan не найден на Chess\.com"):
        await collect_chesscom(FakeChessCom(), "ivan", 1, today=date(2026, 1, 1))

    def broken(status: int, body: str) -> FakeChessCom:
        class Broken(FakeChessCom):
            def __call__(self, request: httpx.Request) -> httpx.Response:
                return httpx.Response(status, text=body)

        return Broken()

    with pytest.raises(UserNotFoundError):
        await collect_chesscom(broken(410, "{}"), "ivan", 1, today=date(2026, 1, 1))
    with pytest.raises(SourceError, match="ответ 403"):
        await collect_chesscom(broken(403, "{}"), "ivan", 1, today=date(2026, 1, 1))
    with pytest.raises(SourceError, match="некорректный ответ"):
        await collect_chesscom(broken(200, "not json"), "ivan", 1, today=date(2026, 1, 1))
    with pytest.raises(SourceError, match="некорректный ответ"):
        await collect_chesscom(broken(200, "[1, 2]"), "ivan", 1, today=date(2026, 1, 1))


# --- Разбор ---


def test_convert_sets_source_id_and_user_color() -> None:
    game = SourceGame(external_id="abc12345", pgn=make_pgn("Opp", "Judy", date="2026.03.04"))

    imported = convert(game, "judy")

    assert isinstance(imported, ImportedGame)
    assert imported.external_id == "abc12345"
    assert imported.user_color == Color.BLACK
    assert imported.white_elo == 1500
    assert imported.time_control == "300+3"
    assert imported.opening_name is not None
    assert imported.played_at is not None
    assert imported.played_at.date() == date(2026, 3, 4)


def test_convert_skips_variants_and_broken_games() -> None:
    good = SourceGame("a", make_pgn("kim", "x"))
    from_position = SourceGame(
        "b",
        make_pgn(
            "kim",
            "x",
            moves="1. e4 Kd7",
            extra=(
                '[Variant "From Position"]\n[SetUp "1"]\n[FEN "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"]\n'
            ),
        ),
    )
    games = [
        good,
        from_position,
        SourceGame("c", make_pgn("kim", "x"), standard=False),
        SourceGame("d", make_pgn("kim", "x", moves="")),
        SourceGame("e", make_pgn("kim", "x", moves="1. e4 e5 2. Ke3 Ke6")),
        SourceGame("f", ""),
    ]

    converted = convert_page(games, "KIM")

    assert [game.external_id for game in converted] == ["a", "b"]
    assert all(game.user_color == Color.WHITE for game in converted)
