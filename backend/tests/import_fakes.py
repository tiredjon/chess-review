"""Фейковые Lichess и Chess.com для тестов импорта (httpx.MockTransport)."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.importers.http import RetryPolicy

Handler = Callable[[httpx.Request], httpx.Response]


async def no_sleep(_: float) -> None:
    return None


FAST_RETRY = RetryPolicy(attempts=3, rate_limit_wait_s=0, backoff_s=0, sleep=no_sleep)


def make_pgn(
    white: str,
    black: str,
    *,
    date: str = "2026.10.01",
    moves: str = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6",
    result: str = "*",
    extra: str = "",
) -> str:
    return (
        f'[Event "Rated blitz game"]\n[Site "?"]\n[Date "{date}"]\n[Round "-"]\n'
        f'[White "{white}"]\n[Black "{black}"]\n[Result "{result}"]\n'
        f'[UTCDate "{date}"]\n[UTCTime "12:00:00"]\n[WhiteElo "1500"]\n[BlackElo "1600"]\n'
        f'[TimeControl "300+3"]\n{extra}\n{moves} {result}\n'
    )


@dataclass
class FakeLichess:
    """`GET /api/games/user/{name}`: партии новые первыми, `max`, `until` (исключающий)."""

    users: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    # Ответы, которые отдаются вместо нормального (по одному на запрос).
    failures: list[httpx.Response] = field(default_factory=list)

    def add_games(self, username: str, count: int, *, start_ms: int = 1_790_000_000_000) -> None:
        games = self.users.setdefault(username.lower(), [])
        for i in range(count):
            created = start_ms - i * 60_000
            games.append(
                {
                    "id": f"g{username[:3]}{len(games):04d}",
                    "variant": "standard",
                    "createdAt": created,
                    "pgn": make_pgn(username, f"opp{i}"),
                }
            )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.failures:
            return self.failures.pop(0)
        prefix = "/api/games/user/"
        if not request.url.path.startswith(prefix):
            return httpx.Response(404)
        games = self.users.get(request.url.path.removeprefix(prefix).lower())
        if games is None:
            return httpx.Response(404, json={"error": "Not found"})
        params = request.url.params
        if "until" in params:
            games = [g for g in games if g["createdAt"] < int(params["until"])]
        games = games[: int(params.get("max", len(games)))]
        body = "".join(json.dumps(g) + "\n" for g in games)
        return httpx.Response(200, text=body, headers={"Content-Type": "application/x-ndjson"})


@dataclass
class FakeChessCom:
    """`/pub/player/{name}/games/archives` и `/pub/player/{name}/games/{YYYY}/{MM}`."""

    # username (lower) -> {(year, month): [game json]}
    users: dict[str, dict[tuple[int, int], list[dict[str, Any]]]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    base: str = "https://api.chess.com"

    def add_game(
        self,
        username: str,
        year: int,
        month: int,
        game_id: int,
        *,
        white: str | None = None,
        black: str = "opponent",
        rules: str = "chess",
        accuracies: dict[str, float] | None = None,
    ) -> None:
        months = self.users.setdefault(username.lower(), {})
        white = white or username
        months.setdefault((year, month), []).append(
            {
                "url": f"https://www.chess.com/game/live/{game_id}",
                "uuid": f"uuid-{game_id}",
                "end_time": 1_700_000_000 + game_id,
                "rules": rules,
                "pgn": make_pgn(white, black, date=f"{year}.{month:02d}.01"),
                "white": {"username": white},
                "black": {"username": black},
                **({"accuracies": accuracies} if accuracies is not None else {}),
            }
        )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        parts = request.url.path.strip("/").split("/")
        # pub / player / {name} / games / archives | {YYYY}/{MM}
        if parts[:2] != ["pub", "player"] or len(parts) < 5:
            return httpx.Response(404)
        name = parts[2]
        if name != name.lower():
            return httpx.Response(301)
        months = self.users.get(name)
        if months is None:
            return httpx.Response(404, json={"code": 0, "message": "not found"})
        if parts[4] == "archives":
            urls = [
                f"{self.base}/pub/player/{name}/games/{y:04d}/{m:02d}" for y, m in sorted(months)
            ]
            return httpx.Response(200, json={"archives": urls})
        key = (int(parts[4]), int(parts[5]))
        return httpx.Response(200, json={"games": months.get(key, [])})


def mock_client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def routed(lichess: Handler, chesscom: Handler) -> Handler:
    """Один транспорт на оба источника — как общий httpx-клиент воркера."""

    def handler(request: httpx.Request) -> httpx.Response:
        return chesscom(request) if request.url.host == "api.chess.com" else lichess(request)

    return handler
