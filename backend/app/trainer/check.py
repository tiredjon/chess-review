"""Проверка ответа ученика: ход курса, равноценная альтернатива или ошибка.

Оценки движка — чистые функции над `chess.engine.Score`; сам движок подключается через
`PositionEngine` (в тестах — фейк)."""

from dataclasses import dataclass
from typing import Literal

import chess
from chess.engine import Score

from app.engine.analyzer import PositionEngine
from app.engine.cache import EvalCache, fen_key
from app.review.evaluate import terminal_eval
from app.review.types import PositionEval
from app.review.winprob import win_percent

Verdict = Literal["main", "alternative", "wrong"]


class IllegalMoveError(ValueError):
    """Ход не разбирается как UCI или нелегален в позиции."""


def parse_move(board: chess.Board, uci: str) -> chess.Move:
    try:
        move = chess.Move.from_uci(uci)
    except ValueError as exc:
        raise IllegalMoveError(f"Некорректный ход: {uci}") from exc
    if not board.is_legal(move):
        raise IllegalMoveError(f"Нелегальный ход: {uci}")
    return move


def win_loss(best: Score, after_opponent: Score) -> float:
    """Потеря win% учеником. `best` — оценка позиции до хода (глазами ученика),
    `after_opponent` — позиции после хода (глазами соперника, он на ходу). Не меньше 0."""
    return max(0.0, win_percent(best) - (100.0 - win_percent(after_opponent)))


def classify_answer(*, in_course: bool, loss: float | None, threshold: float) -> Verdict:
    """main — ход среди ходов курса; иначе alternative, если потеря не больше порога
    (граница включительно), иначе wrong. Для ответа вне курса `loss` обязателен."""
    if in_course:
        return "main"
    if loss is None:
        raise ValueError("для хода вне курса нужна потеря win%")
    return "alternative" if loss <= threshold else "wrong"


@dataclass(frozen=True, slots=True)
class Evaluator:
    """Оценка позиции: финальная — без движка, затем кэш, затем движок (MultiPV=1)."""

    engine: PositionEngine
    cache: EvalCache
    depth: int

    async def evaluate(self, board: chess.Board) -> PositionEval:
        final = terminal_eval(board)
        if final is not None:
            return final
        key = fen_key(board)
        cached = await self.cache.get(key, self.depth, 1)
        if cached is not None:
            return cached
        result = await self.engine.analyse(board, depth=self.depth, multipv=1)
        await self.cache.put(key, self.depth, 1, result)
        return result

    async def loss_of(self, board: chess.Board, move: chess.Move) -> float:
        """Потеря win% ученика от хода `move` против лучшего хода в позиции."""
        best = await self.evaluate(board)
        after = board.copy(stack=False)
        after.push(move)
        return win_loss(best.score, (await self.evaluate(after)).score)
