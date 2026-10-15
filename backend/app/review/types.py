"""Доменные типы разбора. Без I/O: движок и БД зависят от них, а не наоборот."""

from dataclasses import dataclass
from enum import StrEnum

import chess
from chess.engine import Score


class MoveClass(StrEnum):
    BOOK = "book"
    FORCED = "forced"
    BRILLIANT = "brilliant"
    GREAT = "great"
    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


class Phase(StrEnum):
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


@dataclass(frozen=True, slots=True)
class EngineLine:
    """Одна линия MultiPV. Оценка — с точки зрения стороны, которая ходит в позиции."""

    score: Score
    pv: tuple[chess.Move, ...]


@dataclass(frozen=True, slots=True)
class PositionEval:
    """Оценка позиции с точки зрения стороны, которая в ней ходит.

    Для финальной позиции (мат, пат, ничья по правилам) движок не вызывается:
    `lines` пуст, а `score` — Mate(0) для получившего мат или Cp(0) для ничьей.
    """

    score: Score
    lines: tuple[EngineLine, ...] = ()
    depth: int = 0

    @property
    def best_move(self) -> chess.Move | None:
        if not self.lines or not self.lines[0].pv:
            return None
        return self.lines[0].pv[0]
