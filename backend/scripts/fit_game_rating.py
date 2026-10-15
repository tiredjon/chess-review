"""Подбор модели рейтинга партии (`app/review/game_rating.py`) по парам (рейтинг, точность
Chess.com) из `scripts/collect_chesscom_accuracy.py`.

Модель — ожидаемая точность игрока данного рейтинга, своя кривая на каждый контроль:
  E[точность | r] = a − b·e^(−r/c),
подбирается по средним в диапазонах рейтинга шириной BIN (вес диапазона ограничен, чтобы
плотная середина не диктовала форму); daily — кривая рапида со сдвигом (партий мало).
Рейтинг партии — обратная функция: какой рейтинг в среднем играет с такой точностью
(так же ведёт себя «Game Rating» Chess.com: 77 → ~1750, 71 → ~1250 в рапиде).

    PYTHONPATH=. uv run python scripts/fit_game_rating.py data.jsonl
"""

import json
import math
import sys
from collections import defaultdict

from scripts.fitting import nelder_mead

CLASSES = ("rapid", "blitz", "bullet", "daily")


def expected(rating: float, a: float, b: float, c: float, offset: float) -> float:
    return a - b * math.exp(-rating / c) + offset


BIN = 100
# Вес диапазона рейтинга — не больше MAX_WEIGHT точек, чтобы плотная середина не диктовала форму.
MAX_WEIGHT = 200
MIN_POINTS = 20


def fit_class(points: list[tuple[int, float]]) -> tuple[float, float, float]:
    bins: dict[int, list[float]] = defaultdict(list)
    for rating, accuracy in points:
        bins[rating // BIN * BIN + BIN // 2].append(accuracy)
    means = [
        (center, sum(v) / len(v), min(len(v), MAX_WEIGHT))
        for center, v in bins.items()
        if len(v) >= MIN_POINTS
    ]

    def objective(x: list[float]) -> float:
        a, b, c = x
        if not (60 < a < 110 and 0 < b < 200 and 100 < c < 6000):
            return 1e12
        total = sum(w for _, _, w in means)
        return sum(w * (expected(r, a, b, c, 0) - m) ** 2 for r, m, w in means) / total

    a, b, c = nelder_mead(objective, [90, 40, 1500], [5, 10, 400], 3000)
    return a, b, c


def main() -> None:
    with open(sys.argv[1]) as source:
        rows = [json.loads(line) for line in source]
    rows = [r for r in rows if r["time_class"] in CLASSES and 100 <= r["rating"] <= 3300]
    print(f"точек: {len(rows)}")
    curves: dict[str, tuple[float, float, float]] = {}
    for tc in ("rapid", "blitz", "bullet"):
        points = [(r["rating"], r["accuracy"]) for r in rows if r["time_class"] == tc]
        curves[tc] = fit_class(points)
    # Daily партий мало: кривая рапида со средним сдвигом.
    daily = [r for r in rows if r["time_class"] == "daily"]
    shift = (
        sum(r["accuracy"] - expected(r["rating"], *curves["rapid"], 0) for r in daily) / len(daily)
        if daily
        else 0.0
    )
    listed = ", ".join(f"{k!r}: ({a:.4f}, {b:.4f}, {c:.2f})" for k, (a, b, c) in curves.items())
    print(f"CURVES = {{{listed}}}")
    print(f"DAILY_SHIFT = {shift:.3f}  (daily: {len(daily)})")

    bins: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in rows:
        bins[(r["time_class"], r["rating"] // 200 * 200)].append(r["accuracy"])
    for tc in ("rapid", "blitz", "bullet"):
        line = [
            f"{lo}: {sum(v) / len(v):.1f}/{expected(lo + 100, *curves[tc], 0):.1f}"
            for (cls, lo), v in sorted(bins.items())
            if cls == tc and len(v) >= MIN_POINTS
        ]
        print(tc, "факт/модель:", "; ".join(line))

    def inverse(acc: float, tc: str) -> float:
        a, b, c = curves[tc]
        gap = a - acc
        return 3200.0 if gap <= 0 else min(3200.0, max(100.0, -c * math.log(gap / b)))

    for acc in (60, 65, 70, 71.37, 75, 77.23, 80, 85, 90):
        print(
            f"{acc}: рапид {inverse(acc, 'rapid'):.0f}, блиц {inverse(acc, 'blitz'):.0f}, "
            f"пуля {inverse(acc, 'bullet'):.0f}"
        )


if __name__ == "__main__":
    main()
