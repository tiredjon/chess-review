"""Lichess Opening Explorer по HTTP: статистика ходов мастеров / игроков Lichess и PGN партий.

Вежливость к Lichess: свой User-Agent (клиент из `make_http_client`), один запрос за раз на
экземпляр (на процесс — `make_explorer` отдаёт один экземпляр на API и на воркер), пауза
`explorer_min_interval_s` между запросами. Повторы (429, 5xx, сеть) — общие с импортом
(`app/importers/http.py`); после последней неудачи — `ExplorerUnavailableError`.

Живые ответы разобраны по полям: `moves[].uci/san/white/draws/black/averageRating`,
`topGames[].id/winner/white{name,rating}/black{…}/year/uci`, `opening{eco,name}`.
Замечание на 2026-11: база `lichess` отвечает 401 без токена, `masters` — без токена, 200.
"""

import asyncio
import io
import time
from collections.abc import Awaitable, Callable
from typing import Any

import chess
import chess.pgn
import httpx
import structlog

from app.core.config import Settings
from app.explorer.types import (
    ExplorerMove,
    ExplorerPosition,
    ExplorerSource,
    ExplorerUnavailableError,
    MasterGamePgn,
    MasterGameRef,
)
from app.importers.http import RetryPolicy, SourceError, get_with_retry

log = structlog.get_logger(__name__)

# Параметры запросов: ходов в ответе и партий-образцов у мастеров.
MOVES_LIMIT = 12
TOP_GAMES = 4
# Партии Lichess: быстрые и классика, сильные игроки. Ключ кэша — `LICHESS_PARAMS_KEY`.
LICHESS_SPEEDS = "blitz,rapid,classical"
LICHESS_RATINGS = "2000,2200,2500"
LICHESS_PARAMS_KEY = f"{LICHESS_SPEEDS}|{LICHESS_RATINGS}"


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_move(raw: dict[str, Any]) -> ExplorerMove:
    return ExplorerMove(
        uci=str(raw["uci"]),
        san=str(raw["san"]),
        white=int(raw["white"]),
        draws=int(raw["draws"]),
        black=int(raw["black"]),
        average_rating=_int_or_none(raw.get("averageRating")),
    )


def parse_game_ref(raw: dict[str, Any]) -> MasterGameRef:
    white, black = raw.get("white") or {}, raw.get("black") or {}
    winner = raw.get("winner")
    return MasterGameRef(
        id=str(raw["id"]),
        white=str(white.get("name", "?")),
        black=str(black.get("name", "?")),
        white_rating=_int_or_none(white.get("rating")),
        black_rating=_int_or_none(black.get("rating")),
        year=_int_or_none(raw.get("year")),
        winner="white" if winner == "white" else "black" if winner == "black" else None,
        uci=str(raw["uci"]) if raw.get("uci") else None,
    )


def parse_position(source: ExplorerSource, data: dict[str, Any]) -> ExplorerPosition:
    opening = data.get("opening") or {}
    return ExplorerPosition(
        source=source,
        white=int(data["white"]),
        draws=int(data["draws"]),
        black=int(data["black"]),
        moves=tuple(parse_move(m) for m in data.get("moves", [])),
        top_games=tuple(parse_game_ref(g) for g in data.get("topGames", [])),
        opening_eco=opening.get("eco"),
        opening_name=opening.get("name"),
    )


def parse_master_pgn(game_id: str, pgn: str) -> MasterGamePgn:
    """Игроки, рейтинги, год и результат — из заголовков PGN."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("пустой PGN")
    headers = game.headers

    def rating(name: str) -> int | None:
        value = headers.get(name, "")
        return int(value) if value.isdigit() else None

    year_text = headers.get("Date", "")[:4]
    return MasterGamePgn(
        id=game_id,
        pgn=pgn.strip(),
        white=headers.get("White", "?"),
        black=headers.get("Black", "?"),
        white_rating=rating("WhiteElo"),
        black_rating=rating("BlackElo"),
        year=int(year_text) if year_text.isdigit() else None,
        result=headers.get("Result", "*"),
    )


class LichessExplorer:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str,
        min_interval_s: float,
        policy: RetryPolicy,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._min_interval_s = min_interval_s
        self._policy = policy
        self._clock = clock
        self._lock = asyncio.Lock()
        self._last_request_at: float | None = None

    @classmethod
    def from_settings(cls, settings: Settings, http: httpx.AsyncClient) -> "LichessExplorer":
        return cls(
            http,
            base_url=settings.explorer_api_url,
            min_interval_s=settings.explorer_min_interval_s,
            policy=RetryPolicy.from_settings(settings),
        )

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        sleep: Callable[[float], Awaitable[None]] = self._policy.sleep
        async with self._lock:
            if self._last_request_at is not None:
                wait = self._min_interval_s - (self._clock() - self._last_request_at)
                if wait > 0:
                    await sleep(wait)
            try:
                response = await get_with_retry(
                    self._http,
                    f"{self._base_url}{path}",
                    source="Lichess Explorer",
                    policy=self._policy,
                    params=params,
                )
            except SourceError as exc:
                raise ExplorerUnavailableError(str(exc)) from exc
            finally:
                self._last_request_at = self._clock()
        if response.status_code != httpx.codes.OK:
            raise ExplorerUnavailableError(f"Lichess Explorer: ответ {response.status_code}")
        return response

    async def position(
        self, board: chess.Board, *, source: ExplorerSource = ExplorerSource.MASTERS
    ) -> ExplorerPosition:
        params: dict[str, Any] = {"fen": board.fen(), "moves": MOVES_LIMIT}
        if source is ExplorerSource.MASTERS:
            params["topGames"] = TOP_GAMES
        else:
            params |= {
                "variant": "standard",
                "speeds": LICHESS_SPEEDS,
                "ratings": LICHESS_RATINGS,
                "topGames": 0,
                "recentGames": 0,
            }
        response = await self._get(f"/{source.value}", params)
        try:
            return parse_position(source, response.json())
        except (ValueError, KeyError, TypeError) as exc:
            raise ExplorerUnavailableError("Lichess Explorer: неожиданный ответ") from exc

    async def master_game(self, game_id: str) -> MasterGamePgn:
        response = await self._get(f"/masters/pgn/{game_id}")
        try:
            return parse_master_pgn(game_id, response.text)
        except ValueError as exc:
            raise ExplorerUnavailableError("Lichess Explorer: неожиданный PGN") from exc
