"""Повторение карточек: коробки Лейтнера пазлов (`app/puzzles/srs.py`) с исходом тренажёра."""

from datetime import datetime

from app.puzzles.srs import Review, schedule
from app.trainer.check import Verdict

# Коробка, начиная с которой позиция считается выученной (сводка).
LEARNED_BOX = 3


def review_after(box: int, verdict: Verdict, *, hint_used: bool, now: datetime) -> Review:
    """main — как «решён»; alternative — как «решён с подсказкой» (коробка не растёт);
    wrong — коробка 0, повтор через 10 минут. Подсказка делает и main «с подсказкой»."""
    if verdict == "wrong":
        return schedule(box, solved=False, hint_used=hint_used, now=now)
    return schedule(box, solved=True, hint_used=hint_used or verdict == "alternative", now=now)
