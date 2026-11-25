"""Фейки для сборщика курсов: «база мастеров» из заданных партий и детерминированный движок.

`GamesExplorer` считает статистику позиции по списку линий с весами — как Opening Explorer
по своим партиям: ходы из позиции (по EPD, переходы распознаются), их число партий,
`topGames` — линии, прошедшие через позицию. Линия с весом `n` — n одинаковых партий."""

import asyncio
from collections import Counter
from collections.abc import Collection, Sequence

import chess
from chess.engine import Cp

from app.engine.cache import fen_key
from app.explorer.types import (
    ExplorerMove,
    ExplorerPosition,
    ExplorerSource,
    ExplorerUnavailableError,
    MasterGamePgn,
    MasterGameRef,
)
from app.review.types import EngineLine, PositionEval

NAJDORF = "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6"
ROSSOLIMO = "e2e4 c7c5 g1f3 b8c6 f1b5"
ITALIAN = "e2e4 e7e5 g1f3 b8c6 f1c4"

# Продолжения мастеров (линия от начальной позиции, число партий).
NAJDORF_GAMES: list[tuple[str, int]] = [
    # 6. Be3 — английская атака (41%)
    (NAJDORF + " c1e3 e7e5 d4b3 c8e6 f2f3 f8e7 d1d2 e8g8 e1c1 b8d7 g2g4 b7b5", 40),
    # 6. Bg5 (31%): за чёрных у мастеров 6… e6 (25) и 6… Nbd7 (5)
    (NAJDORF + " c1g5 e7e6 f2f4 f8e7 d1f3 d8c7 e1c1 b8d7", 25),
    (NAJDORF + " c1g5 b8d7 f1c4 d8a5", 5),
    # 6. Be2 (20%)
    (NAJDORF + " f1e2 e7e5 d4b3 f8e7 e1g1 e8g8", 20),
    # 6. h3 (8%) — меньше порога доли
    (NAJDORF + " h2h3 e7e5 d4e2 h7h5", 8),
]
ROSSOLIMO_GAMES: list[tuple[str, int]] = [
    (ROSSOLIMO + " g7g6 b5c6 d7c6 d2d3 f8g7 h2h3 g8f6 b1c3 e8g8 c1e3 b7b6", 50),
    (ROSSOLIMO + " e7e6 e1g1 g8e7 f1e1 a7a6 b5f1 d7d5", 30),
    (ROSSOLIMO + " d7d6 e1g1 c8d7 f1e1 g8f6 c2c3 a7a6", 20),
]
ITALIAN_GAMES: list[tuple[str, int]] = [
    (ITALIAN + " f8c5 c2c3 g8f6 d2d3 d7d6 e1g1 a7a6 a2a4 e8g8 f1e1 c5a7 h2h3 h7h6", 60),
    (ITALIAN + " g8f6 d2d3 f8e7 e1g1 e8g8 f1e1 d7d6 a2a4", 30),
    (ITALIAN + " f8e7 d2d4 d7d6 d4d5 c6b8", 10),
]


def _game_id(index: int) -> str:
    return f"game{index:04d}"


class GamesExplorer:
    """`OpeningExplorer` над списком партий (см. модуль)."""

    def __init__(
        self,
        games: Sequence[tuple[str, int]],
        *,
        fail: bool = False,
        fail_games: bool = False,
        delay_s: float = 0.0,
    ) -> None:
        self.fail = fail
        self.fail_games = fail_games
        self.delay_s = delay_s
        self.position_calls = 0
        self.game_calls: list[str] = []
        # EPD позиции → (ход → партий, id партий через позицию с её ходом)
        self._moves: dict[str, Counter[str]] = {}
        self._games: dict[str, list[tuple[str, str]]] = {}
        self._lines: dict[str, list[str]] = {}
        for index, (line, count) in enumerate(games):
            ucis = line.split()
            self._lines[_game_id(index)] = ucis
            board = chess.Board()
            for uci in ucis:
                epd = board.epd()
                self._moves.setdefault(epd, Counter())[uci] += count
                self._games.setdefault(epd, []).append((_game_id(index), uci))
                board.push_uci(uci)  # нелегальный ход в данных — ошибка теста

    async def position(
        self, board: chess.Board, *, source: ExplorerSource = ExplorerSource.MASTERS
    ) -> ExplorerPosition:
        self.position_calls += 1
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.fail:
            raise ExplorerUnavailableError("тест")
        counts = self._moves.get(board.epd(), Counter())
        moves = tuple(
            ExplorerMove(
                uci=uci,
                san=board.san(chess.Move.from_uci(uci)),
                white=n // 2,
                draws=n - n // 2 - n // 4,
                black=n // 4,
                average_rating=2600,
            )
            for uci, n in counts.most_common()
        )
        refs = tuple(
            MasterGameRef(
                id=game_id,
                white="White, A",
                black="Black, B",
                white_rating=2700,
                black_rating=2650,
                year=2020,
                winner="white",
                uci=uci,
            )
            for game_id, uci in self._games.get(board.epd(), [])[:4]
        )
        total = sum(counts.values())
        return ExplorerPosition(
            source=source,
            white=total // 2,
            draws=total - total // 2 - total // 4,
            black=total // 4,
            moves=moves,
            top_games=refs,
            opening_eco=None,
            opening_name=None,
        )

    async def master_game(self, game_id: str) -> MasterGamePgn:
        self.game_calls.append(game_id)
        if self.fail_games:
            raise ExplorerUnavailableError("тест")
        board = chess.Board()
        moves = [chess.Move.from_uci(uci) for uci in self._lines[game_id]]
        pgn = board.variation_san(moves)
        return MasterGamePgn(
            id=game_id,
            pgn=f'[White "White, A"]\n[Black "Black, B"]\n[Result "1-0"]\n\n{pgn} 1-0',
            white="White, A",
            black="Black, B",
            white_rating=2700,
            black_rating=2650,
            year=2020,
            result="1-0",
        )

    def passes(self, game_id: str, board: chess.Board) -> bool:
        """Прошла ли партия через позицию."""
        replay = chess.Board()
        for uci in self._lines[game_id]:
            if replay.epd() == board.epd():
                return True
            replay.push_uci(uci)
        return replay.epd() == board.epd()


class FakeEngine:
    """Оценка — из словаря «EPD → сантипешки стороне на ходу» (по умолчанию 0); лучший ход —
    из словаря «EPD → uci», иначе первый легальный по алфавиту UCI (детерминированно)."""

    def __init__(
        self,
        scores: dict[str, int] | None = None,
        best: dict[str, str] | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self.scores = scores or {}
        self.best = best or {}
        self.fail = fail
        self.calls = 0

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        exclude: Collection[chess.Move] = (),
    ) -> PositionEval:
        self.calls += 1
        if self.fail:
            raise FileNotFoundError("stockfish")
        key = fen_key(board)
        score = Cp(self.scores.get(key, 0))
        uci = self.best.get(key)
        move = chess.Move.from_uci(uci) if uci else min(board.legal_moves, key=lambda m: m.uci())
        return PositionEval(score=score, lines=(EngineLine(score=score, pv=(move,)),), depth=depth)


def board_after(line: str) -> chess.Board:
    board = chess.Board()
    for uci in line.split():
        board.push_uci(uci)
    return board
