"""Интервальное повторение пазлов — коробки Лейтнера.

Коробка 0 — новый пазл или решённый неверно, 1…5 — следующий показ через 1, 3, 7, 16, 35 дней.
Решён без подсказки — коробка +1; с подсказкой — коробка не растёт (но не ниже 1); не решён
(неверный ход или «показать решение») — коробка 0 и повтор через 10 минут, в этой же сессии
после других пазлов.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

BOX_INTERVALS = (
    timedelta(days=1),
    timedelta(days=3),
    timedelta(days=7),
    timedelta(days=16),
    timedelta(days=35),
)
RELEARN_DELAY = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class Review:
    box: int
    next_review_at: datetime


def schedule(box: int, *, solved: bool, hint_used: bool, now: datetime) -> Review:
    if not solved:
        return Review(box=0, next_review_at=now + RELEARN_DELAY)
    new_box = max(box, 1) if hint_used else min(box + 1, len(BOX_INTERVALS))
    return Review(box=new_box, next_review_at=now + BOX_INTERVALS[new_box - 1])
