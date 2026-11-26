"""Таблицы Syzygy через Lichess tablebase (`tablebase.lichess.ovh/standard`): разбор ответа,
порядок ходов, HTTP-клиент с вежливостью и кэш в БД.

Ответ Lichess: `category`, `dtz`, `dtm` — с точки зрения стороны на ходу; у ходов
(`moves[]`) — с точки зрения стороны, которая ходит **после** хода (соперника). Наружу всё
отдаётся глазами ходящего: категория хода переворачивается, `dtz` / `dtm` меняют знак.

Категории сводятся к шести: `win`, `cursed-win` (выигрыш, но ничья по правилу 50 ходов),
`draw`, `blessed-loss`, `loss`, `unknown`. Неточные `maybe-win` / `syzygy-win` (DTZ округлён)
считаются выигрышем, `maybe-loss` / `syzygy-loss` — проигрышем.

Счётчик 50 ходов в запрос не передаётся (всегда `0 1`): ответ зависит только от расстановки,
поэтому кэш по EPD корректен. Ничью по правилу 50 ходов на доске фронт определяет сам.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

import chess
import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings
from app.db.models import TablebaseCacheEntry
from app.db.session import Database
from app.importers.http import RetryPolicy, SourceError, get_with_retry

log = structlog.get_logger(__name__)

TB_MAX_PIECES = 7

TbCategory = Literal["win", "cursed-win", "draw", "blessed-loss", "loss", "unknown"]

_NORMALIZE: dict[str, TbCategory] = {
    "win": "win",
    "maybe-win": "win",
    "syzygy-win": "win",
    "cursed-win": "cursed-win",
    "draw": "draw",
    "blessed-loss": "blessed-loss",
    "loss": "loss",
    "maybe-loss": "loss",
    "syzygy-loss": "loss",
    "unknown": "unknown",
}
_FLIP: dict[TbCategory, TbCategory] = {
    "win": "loss",
    "cursed-win": "blessed-loss",
    "draw": "draw",
    "blessed-loss": "cursed-win",
    "loss": "win",
    "unknown": "unknown",
}
# Чем меньше, тем лучше для ходящего. `unknown` — между ничьей и спасённым проигрышем.
_RANK: dict[TbCategory, int] = {
    "win": 0,
    "cursed-win": 1,
    "draw": 2,
    "unknown": 3,
    "blessed-loss": 4,
    "loss": 5,
}


class TablebaseUnavailableError(Exception):
    """Lichess tablebase не ответил (сеть, 5xx, 429 после повторов, неожиданный ответ)."""


@dataclass(frozen=True, slots=True)
class TbMove:
    uci: str
    san: str
    # Глазами ходящего: `win` — этот ход выигрывает.
    category: TbCategory
    dtz: int | None
    dtm: int | None
    checkmate: bool = False


@dataclass(frozen=True, slots=True)
class TbPosition:
    category: TbCategory
    dtz: int | None
    dtm: int | None
    checkmate: bool
    stalemate: bool
    # От лучшего хода к худшему для ходящего (`rank_moves`).
    moves: tuple[TbMove, ...]


class Tablebase(Protocol):
    async def probe(self, board: chess.Board) -> TbPosition: ...


def normalize(category: object) -> TbCategory:
    return _NORMALIZE.get(str(category), "unknown")


def flip(category: TbCategory) -> TbCategory:
    return _FLIP[category]


def _neg(value: object) -> int | None:
    return -value if isinstance(value, int) and not isinstance(value, bool) else None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _distance(move: TbMove) -> int:
    """|DTM|, а без него |DTZ| (у 7-фигурных DTM нет); мат — 0."""
    if move.checkmate:
        return 0
    value = move.dtm if move.dtm is not None else move.dtz
    return abs(value) if value is not None else 0


def _move_key(move: TbMove) -> tuple[int, int]:
    rank = _RANK[move.category]
    distance = _distance(move)
    # Выигрыш — быстрее (мат раньше); проигрыш — самая упорная защита (дольше).
    if move.category in ("win", "cursed-win"):
        return rank, distance
    if move.category in ("loss", "blessed-loss"):
        return rank, -distance
    return rank, 0


def rank_moves(moves: list[TbMove]) -> tuple[TbMove, ...]:
    """Лучший ход для ходящего первым: категория, затем быстрейший выигрыш / дольше всего
    держащийся проигрыш. Равные — в порядке Lichess (сортировка устойчивая)."""
    return tuple(sorted(moves, key=_move_key))


def parse_position(data: dict[str, Any]) -> TbPosition:
    """Ответ Lichess → позиция глазами ходящего."""
    moves = [
        TbMove(
            uci=str(raw["uci"]),
            san=str(raw["san"]),
            category=flip(normalize(raw.get("category"))),
            dtz=_neg(raw.get("dtz")),
            dtm=_neg(raw.get("dtm")),
            checkmate=bool(raw.get("checkmate")),
        )
        for raw in data.get("moves", [])
    ]
    return TbPosition(
        category=normalize(data.get("category")),
        dtz=_int(data.get("dtz")),
        dtm=_int(data.get("dtm")),
        checkmate=bool(data.get("checkmate")),
        stalemate=bool(data.get("stalemate")),
        moves=rank_moves(moves),
    )


def piece_count(board: chess.Board) -> int:
    return chess.popcount(board.occupied)


def query_fen(board: chess.Board) -> str:
    """FEN для запроса и ключа кэша: расстановка, очередь, рокировки, en passant, `0 1`."""
    return f"{board.epd()} 0 1"


class LichessTablebase:
    """HTTP-клиент. Вежливость — как у Explorer: свой User-Agent (`make_http_client`), один
    запрос за раз на экземпляр (экземпляр — один на процесс), пауза `min_interval_s` между
    запросами, повторы 429 (ждать Retry-After или минуту) / 5xx / сеть — `get_with_retry`."""

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
    def from_settings(cls, settings: Settings, http: httpx.AsyncClient) -> "LichessTablebase":
        return cls(
            http,
            base_url=settings.tablebase_api_url,
            min_interval_s=settings.tablebase_min_interval_s,
            policy=RetryPolicy.from_settings(settings),
        )

    async def raw(self, board: chess.Board) -> dict[str, Any]:
        """Ответ Lichess как есть (он и кэшируется)."""
        sleep: Callable[[float], Awaitable[None]] = self._policy.sleep
        async with self._lock:
            if self._last_request_at is not None:
                wait = self._min_interval_s - (self._clock() - self._last_request_at)
                if wait > 0:
                    await sleep(wait)
            try:
                response = await get_with_retry(
                    self._http,
                    f"{self._base_url}/standard",
                    source="Lichess tablebase",
                    policy=self._policy,
                    params={"fen": query_fen(board)},
                )
            except SourceError as exc:
                raise TablebaseUnavailableError(str(exc)) from exc
            finally:
                self._last_request_at = self._clock()
        if response.status_code != httpx.codes.OK:
            raise TablebaseUnavailableError(f"Lichess tablebase: ответ {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise TablebaseUnavailableError("Lichess tablebase: не JSON") from exc
        if not isinstance(data, dict) or "category" not in data:
            raise TablebaseUnavailableError("Lichess tablebase: неожиданный ответ")
        return data

    async def probe(self, board: chess.Board) -> TbPosition:
        return parse_position(await self.raw(board))


class RawTablebase(Protocol):
    async def raw(self, board: chess.Board) -> dict[str, Any]: ...


class CachedTablebase:
    """Сначала `tablebase_cache` (ответ таблиц не устаревает), потом Lichess."""

    def __init__(
        self,
        inner: RawTablebase,
        db: Database,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._inner = inner
        self._db = db
        self._now = now

    async def probe(self, board: chess.Board) -> TbPosition:
        epd = board.epd()
        async with self._db.sessionmaker() as session:
            row = await session.get(TablebaseCacheEntry, epd)
            if row is not None:
                return parse_position(row.data)
        data = await self._inner.raw(board)
        stmt = (
            insert(TablebaseCacheEntry)
            .values(epd=epd, data=data, fetched_at=self._now())
            .on_conflict_do_nothing()
        )
        async with self._db.sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()
        return parse_position(data)


def make_tablebase(settings: Settings, http: httpx.AsyncClient, db: Database) -> CachedTablebase:
    return CachedTablebase(LichessTablebase.from_settings(settings, http), db)
