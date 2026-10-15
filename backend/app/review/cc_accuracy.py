"""Точность «как у Chess.com» — приближение их закрытой формулы (CAPS2).

Схема та же, что у Lichess (`accuracy.py`): потеря шансов за ход → точность хода → точность
партии, но параметры подобраны по партиям, у которых известна официальная точность
Chess.com (`scripts/fit_accuracy.py`). Официальную точность, когда она есть, API отдаёт
отдельно (`games.source_*_accuracy`); эта — для остальных партий.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from chess.engine import Score

# Оценка обрезается, мат — как ±CP_CAP.
CP_CAP = 1000.0
# Нижняя граница точности хода в степенном среднем (при p ≤ 0 ноль недопустим).
MIN_MOVE_ACCURACY = 1.0


@dataclass(frozen=True, slots=True)
class CcParams:
    # Крутизна перевода оценки в win% (у Lichess 0.00368208).
    k: float
    # Штраф за потерю win% и сдвиг кривой: точность хода = (100 + c)·e^(−b·Δ) − c.
    b: float
    c: float
    # Степенное среднее по ходам: 1 — обычное, −1 — гармоническое.
    p: float


# Подобраны scripts/fit_accuracy.py (см. SPEC «Принятые решения»).
PARAMS = CcParams(k=0.00130498, b=0.152752, c=5.90481, p=0.393014)


def to_cp(cp: int | float | None, mate: int | None) -> float:
    """Оценка за ходящего в сантипешках; мат — ±CP_CAP (`mate == 0` — ходящий поставил мат)."""
    if mate is not None:
        return CP_CAP if mate >= 0 else -CP_CAP
    return float(max(-CP_CAP, min(CP_CAP, cp or 0)))


def score_cp(score: Score) -> float:
    return to_cp(score.score(), score.mate())


def win_percent(cp: float, k: float) -> float:
    cp = max(-CP_CAP, min(CP_CAP, cp))
    return 50 + 50 * (2 / (1 + math.exp(-k * cp)) - 1)


def move_accuracy(cp_before: float, cp_after: float, params: CcParams) -> float:
    """Оценки до и после хода — за ходящего, в сантипешках."""
    delta = max(0.0, win_percent(cp_before, params.k) - win_percent(cp_after, params.k))
    value = (100 + params.c) * math.exp(-params.b * delta) - params.c
    return max(0.0, min(100.0, value))


def game_accuracy(moves: Sequence[tuple[float, float]], params: CcParams = PARAMS) -> float:
    """Точность игрока за партию по его ходам `(cp_before, cp_after)`."""
    if not moves:
        return 100.0
    values = [max(MIN_MOVE_ACCURACY, move_accuracy(b, a, params)) for b, a in moves]
    if abs(params.p) < 1e-6:
        return math.exp(sum(math.log(v) for v in values) / len(values))
    mean = sum(v**params.p for v in values) / len(values)
    return float(mean ** (1 / params.p))


def side_accuracy(moves: Sequence[tuple[Score, Score]]) -> float | None:
    """Точность стороны по её ходам `(оценка до, оценка после)` за ходящего; None — ходов нет."""
    return game_accuracy([(score_cp(b), score_cp(a)) for b, a in moves]) if moves else None


MoveRow = tuple[bool, int | None, int | None, int | None, int | None]


def color_accuracy(rows: Sequence[MoveRow], *, white: bool) -> float | None:
    """Точность стороны по строкам `(ход белых, cp до, мат до, cp после, мат после)`;
    None — у стороны нет ходов."""
    own = [(to_cp(cb, mb), to_cp(ca, ma)) for is_white, cb, mb, ca, ma in rows if is_white == white]
    return game_accuracy(own) if own else None
