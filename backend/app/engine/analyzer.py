"""Анализ позиций партии: финальные — без движка, остальные — через кэш и пул.

Бюджет времени (SPEC §10) не позволяет MultiPV=3 везде: он примерно втрое дороже
MultiPV=1. Альтернативные линии нужны только для `great` — когда сыгран лучший ход.
Поэтому каждая позиция анализируется с MultiPV=1, а если в партии из неё сыгран
лучший ход, отдельным поиском без этого хода добираются ещё `multipv − 1` линий.
Итог эквивалентен MultiPV=`multipv`, но стоит ~1× на каждую доп. линию и только там,
где она нужна.
"""

import asyncio
from collections.abc import Callable, Collection, Sequence
from typing import Protocol

import chess

from app.engine.cache import EvalCache, fen_key
from app.review.evaluate import terminal_eval
from app.review.types import PositionEval


class PositionEngine(Protocol):
    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        exclude: Collection[chess.Move] = (),
    ) -> PositionEval: ...


ProgressCallback = Callable[[int, int], None]


class Analyzer:
    def __init__(self, engine: PositionEngine, cache: EvalCache | None = None) -> None:
        self.engine = engine
        self.cache = cache

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        played: Collection[chess.Move] = (),
    ) -> PositionEval:
        """Оценка позиции; `played` — ходы, сыгранные из неё в партии.

        Полный набор из `multipv` линий считается, только если среди `played`
        есть лучший ход движка; иначе возвращается одна линия.
        """
        terminal = terminal_eval(board)
        if terminal is not None:
            return terminal
        key = fen_key(board)
        if multipv > 1:
            full = await self._cached(key, depth, multipv)
            if full is not None:
                return full

        base = await self._cached(key, depth, 1)
        if base is None:
            base = await self.engine.analyse(board, depth=depth, multipv=1)
            await self._store(key, depth, 1, base)

        best = base.best_move
        if multipv <= 1 or best is None or best not in played or board.legal_moves.count() < 2:
            return base

        alternatives = await self.engine.analyse(
            board, depth=depth, multipv=multipv - 1, exclude=(best,)
        )
        full = PositionEval(
            score=base.score, lines=base.lines[:1] + alternatives.lines, depth=base.depth
        )
        await self._store(key, depth, multipv, full)
        return full

    async def analyse_game(
        self,
        positions: Sequence[chess.Board],
        moves: Sequence[chess.Move],
        *,
        depth: int,
        multipv: int,
        on_progress: ProgressCallback | None = None,
    ) -> list[PositionEval]:
        """Оценки всех позиций партии (`positions` — на одну больше, чем `moves`).

        Позиции анализируются параллельно (параллелизм ограничен пулом), повторы
        по ключу кэша — один раз. `on_progress(done, total)` — после каждой позиции.
        """
        if len(positions) != len(moves) + 1:
            raise ValueError("позиций должно быть на одну больше, чем ходов")

        results: list[PositionEval | None] = [terminal_eval(board) for board in positions]
        unique: dict[str, tuple[chess.Board, set[chess.Move]]] = {}
        for index, board in enumerate(positions):
            if results[index] is not None:
                continue
            _, played = unique.setdefault(fen_key(board), (board, set()))
            if index < len(moves):
                played.add(moves[index])
        total, done = len(unique), 0

        async def run(board: chess.Board, played: set[chess.Move]) -> PositionEval:
            nonlocal done
            result = await self.analyse(board, depth=depth, multipv=multipv, played=played)
            done += 1
            if on_progress is not None:
                on_progress(done, total)
            return result

        evals = await asyncio.gather(*(run(board, played) for board, played in unique.values()))
        by_key = dict(zip(unique, evals, strict=True))
        return [
            result if result is not None else by_key[fen_key(board)]
            for board, result in zip(positions, results, strict=True)
        ]

    async def _cached(self, key: str, depth: int, multipv: int) -> PositionEval | None:
        return None if self.cache is None else await self.cache.get(key, depth, multipv)

    async def _store(self, key: str, depth: int, multipv: int, value: PositionEval) -> None:
        if self.cache is not None:
            await self.cache.put(key, depth, multipv, value)
