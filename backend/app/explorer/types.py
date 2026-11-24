"""Контракт Opening Explorer (сессия 13). Реализация — `client.py` (HTTP + кэш в БД), в тестах
— фейк по этому же протоколу. Числа — как в ответе Lichess: партий белых побед, ничьих и
побед чёрных после хода."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

import chess


class ExplorerSource(StrEnum):
    # Партии мастеров (2200+ FIDE, OTB) — основной источник продолжений и образцовых партий.
    MASTERS = "masters"
    # Партии Lichess (фильтр по рейтингу) — запасной, когда у мастеров мало партий.
    LICHESS = "lichess"


@dataclass(frozen=True, slots=True)
class ExplorerMove:
    uci: str
    san: str
    white: int
    draws: int
    black: int
    average_rating: int | None

    @property
    def games(self) -> int:
        return self.white + self.draws + self.black


@dataclass(frozen=True, slots=True)
class MasterGameRef:
    """Ссылка на партию мастеров из `topGames`; PGN — `MastersExplorer.game`."""

    id: str
    white: str
    black: str
    white_rating: int | None
    black_rating: int | None
    year: int | None
    winner: Literal["white", "black"] | None
    # Ход, сыгранный в партии из этой позиции.
    uci: str | None


@dataclass(frozen=True, slots=True)
class ExplorerPosition:
    source: ExplorerSource
    white: int
    draws: int
    black: int
    # По убыванию числа партий, как отдаёт Lichess.
    moves: tuple[ExplorerMove, ...]
    # Только у `masters`.
    top_games: tuple[MasterGameRef, ...]
    opening_eco: str | None
    opening_name: str | None

    @property
    def games(self) -> int:
        return self.white + self.draws + self.black


@dataclass(frozen=True, slots=True)
class MasterGamePgn:
    id: str
    pgn: str
    white: str
    black: str
    white_rating: int | None
    black_rating: int | None
    year: int | None
    result: str


class OpeningExplorer(Protocol):
    async def position(
        self, board: chess.Board, *, source: ExplorerSource = ExplorerSource.MASTERS
    ) -> ExplorerPosition:
        """Статистика ходов из позиции. Ошибка сети / 429 после повторов —
        `ExplorerUnavailableError`."""
        ...

    async def master_game(self, game_id: str) -> MasterGamePgn: ...


class ExplorerUnavailableError(Exception):
    """Lichess Explorer не ответил (сеть, 429, 5xx после повторов)."""
