"""Признаки позиции и хода — для модели рейтинга партии с учётом позиций
(`scripts/fit_position_rating.py`, SPEC «Принятые решения»).

Гроссмейстер и игрок 1000 почти не попадают в одни и те же позиции: одна и та же потеря в
спокойной позиции, где почти любой ход хорош, и в острой, где хорош один ход, говорит о
разном уровне. Короткий MultiPV (SHALLOW_DEPTH, SHALLOW_LINES) показывает, сколько в позиции
хороших ходов и насколько сильно наказываются остальные.
"""

import math
from collections.abc import Sequence

from app.review.cc_accuracy import PARAMS, win_percent

SHALLOW_DEPTH = 8
SHALLOW_LINES = 8

FEATURES = ("good", "gap", "spread", "legal", "decided", "punish", "capture", "progress")


def move_features(
    lines: Sequence[float],
    legal: int,
    cp_before: float,
    *,
    previous_loss: float,
    best_is_capture: bool,
    ply: int,
) -> tuple[float, ...]:
    """Признаки позиции перед ходом, в порядке FEATURES.

    `lines` — оценки линий короткого MultiPV за ходящего (сантипешки, лучшая первой),
    `legal` — число легальных ходов, `cp_before` — оценка позиции (основной анализ),
    `previous_loss` — сколько win% потерял соперник предыдущим ходом, `ply` — номер полухода
    (с 0).

    good     — log2 числа ходов, теряющих не больше 3 win%;
    gap      — сколько теряет второй по силе ход (0 — если ход единственный), /10;
    spread   — средняя потеря по линиям: насколько наказываются «обычные» ходы, /10;
    legal    — log2 числа легальных ходов;
    decided  — насколько позиция уже решена: |win% − 50| / 50;
    punish   — потеря соперника предыдущим ходом (до 30 win%), /10: есть что наказать;
    capture  — лучший ход — взятие;
    progress — стадия партии: полуход / 60 (до 2).
    """
    wins = [win_percent(cp, PARAMS.k) for cp in lines] or [win_percent(cp_before, PARAMS.k)]
    losses = [wins[0] - win for win in wins]
    good = sum(1 for loss in losses if loss <= 3.0)
    return (
        math.log2(max(1, good)),
        (losses[1] if len(losses) > 1 else 0.0) / 10,
        sum(losses) / len(losses) / 10,
        math.log2(max(1, legal)),
        abs(win_percent(cp_before, PARAMS.k) - 50) / 50,
        min(previous_loss, 30.0) / 10,
        1.0 if best_is_capture else 0.0,
        min(ply / 60, 2.0),
    )
