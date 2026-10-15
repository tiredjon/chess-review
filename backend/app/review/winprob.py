"""Оценка движка → вероятность выигрыша (SPEC §4.1–4.2, формула Lichess).

Оценки — объекты `chess.engine.Score` с точки зрения какой-то стороны:
`Cp(n)`, `Mate(n)` (n > 0 — эта сторона ставит мат, n < 0 — получает),
`Mate(0)` — мат уже на доске этой стороне, `MateGiven` — эта сторона его поставила.
"""

import math

from chess.engine import Cp, Score

from app.review.thresholds import CP_CEILING, MATE_CP, MATE_STEP_CP

WIN_PERCENT_K = 0.00368208


def score_to_cp(score: Score) -> int:
    """Сантипешки; мат в N → ±(10000 − N·10)."""
    mate = score.mate()
    if mate is None:
        cp = score.score()
        assert cp is not None
        return cp
    # Mate(0) и MateGiven оба дают mate() == 0; различаем сравнением.
    if mate > 0 or (mate == 0 and score > Cp(0)):
        return MATE_CP - mate * MATE_STEP_CP
    return -MATE_CP - mate * MATE_STEP_CP


def win_percent_from_cp(cp: float) -> float:
    cp = max(-CP_CEILING, min(CP_CEILING, cp))
    return 50 + 50 * (2 / (1 + math.exp(-WIN_PERCENT_K * cp)) - 1)


def win_percent(score: Score) -> float:
    return win_percent_from_cp(score_to_cp(score))


def format_score(score: Score) -> str:
    """Для UI: «+0.80», «-3.20», «#3», «#-2»; мат на доске — «#»."""
    mate = score.mate()
    if mate is None:
        return f"{score_to_cp(score) / 100:+.2f}"
    if mate == 0:
        return "#"
    return f"#{mate}"
