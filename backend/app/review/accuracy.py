"""Точность хода и партии (SPEC §4.3–4.4).

Порт `AccuracyPercent.scala` из lila. Сверено с точностью, которую показывает
Lichess, на 984 партиях — совпадение до округления; 46 из них с разными
окончаниями лежат в tests/data/lichess_accuracy.json.
"""

import math
import statistics
from collections.abc import Iterable, Sequence

from app.review.thresholds import (
    VOLATILITY_WEIGHT_MAX,
    VOLATILITY_WEIGHT_MIN,
    VOLATILITY_WINDOW_MAX,
    VOLATILITY_WINDOW_MIN,
)

# Константы из lila (полная точность, а не округлённые из §4.3).
_ACC_A = 103.1668100711649
_ACC_K = -0.04354415386753951
_ACC_B = -3.166924740191411
# «Uncertainty bonus» lila: анализ движка не идеален.
_UNCERTAINTY_BONUS = 1.0


def move_accuracy(win_before: float, win_after: float) -> float:
    """Точность хода по win% до и после него, оба — с точки зрения ходящего."""
    if win_after >= win_before:
        return 100.0
    delta = win_before - win_after
    raw = _ACC_A * math.exp(_ACC_K * delta) + _ACC_B + _UNCERTAINTY_BONUS
    return max(0.0, min(100.0, raw))


def volatility_window(plies: int) -> int:
    """Размер окна: число полуходов / 10 в пределах [2, 8].

    В lila это `cps.size / 10`, где cps — оценки после каждого полухода.
    Именно этот вариант совпадает с точностью Lichess на реальных партиях.
    """
    return max(VOLATILITY_WINDOW_MIN, min(VOLATILITY_WINDOW_MAX, plies // 10))


def volatility_weights(win_percents: Sequence[float]) -> list[float]:
    """Вес каждого хода — stdev win% в скользящем окне.

    `win_percents` — по одной точке на позицию (ходов + 1), с точки зрения
    одной и той же стороны (белых). Возвращает по весу на ход.
    """
    plies = len(win_percents) - 1
    if plies <= 0:
        return []
    size = volatility_window(plies)
    # Первые ходы получают окно с начала партии, дальше окно скользит.
    head = [win_percents[:size]] * (min(size, len(win_percents)) - 2)
    sliding = [win_percents[i : i + size] for i in range(len(win_percents) - size + 1)]
    return [
        max(VOLATILITY_WEIGHT_MIN, min(VOLATILITY_WEIGHT_MAX, statistics.pstdev(window)))
        for window in head + sliding
    ]


def aggregate_accuracy(moves: Iterable[tuple[float, float]]) -> float | None:
    """Точность набора ходов `(accuracy, weight)`: среднее взвешенного и гармонического."""
    items = list(moves)
    if not items:
        return None
    total_weight = sum(weight for _, weight in items)
    weighted = sum(acc * weight for acc, weight in items) / total_weight
    harmonic = len(items) / sum(1 / max(1.0, acc) for acc, _ in items)
    return (weighted + harmonic) / 2
