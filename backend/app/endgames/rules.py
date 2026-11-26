"""Правила отбора позиций из своих партий (SPEC «Сессия 16.3»). Чистые функции, без I/O."""

from app.endgames.catalog import Goal
from app.review.types import MoveClass

# Цель по win% до хода (глазами ходящего): ≥ 65 — выиграть, 35–65 — сделать ничью, ниже —
# позиция и так плохая, тренировать нечего.
WIN_GOAL_MIN = 65.0
DRAW_GOAL_MIN = 35.0

# Ошибка, из-за которой позиция попадает в тренажёр.
SOURCE_CLASSES = (MoveClass.MISTAKE, MoveClass.BLUNDER)


def goal_for(win_before: float) -> Goal | None:
    if win_before >= WIN_GOAL_MIN:
        return "win"
    if win_before >= DRAW_GOAL_MIN:
        return "draw"
    return None
