"""Ключи уроков тренера и какой урок к какой метрике (общий контракт 17.1–17.3).

Тексты уроков — на фронте (`web/src/lib/coach-lessons/`, RU и EN, пишет 17.1), позиции и
тренировка — `GET /coach/lessons/{key}` (17.2), ссылка из слабой стороны — `GapOut.lesson`
(17.1). Статьи по книгам Ласкера и Капабланки (`book`) — с позициями из партий книг
(`app/books/lessons.py`). Новый урок — добавить ключ сюда и текст на фронт.
"""

from typing import Literal

from app.books.lessons import BOOK_LESSONS
from app.review.motifs.base import MotifType

LessonKind = Literal["motif", "phase", "skill", "book"]

PHASE_LESSONS: tuple[str, ...] = ("opening_principles", "middlegame_plans", "endgame_technique")
SKILL_LESSONS: tuple[str, ...] = (
    "blunder_check",
    "tactical_vision",
    "converting_advantage",
    "defense",
    "time_management",
    "opening_repertoire",
)

LESSONS: dict[str, LessonKind] = {
    **{m.value: "motif" for m in MotifType},
    **dict.fromkeys(PHASE_LESSONS, "phase"),
    **dict.fromkeys(SKILL_LESSONS, "skill"),
    **dict.fromkeys(BOOK_LESSONS, "book"),  # статьи по книгам (`app/books/lessons.py`)
}

# Метрика диагностики → урок (`MetricKey` в `app/api/schemas_coach.py`).
METRIC_LESSONS: dict[str, str] = {
    "accuracy": "blunder_check",
    "accuracy_opening": "opening_principles",
    "accuracy_middlegame": "middlegame_plans",
    "accuracy_endgame": "endgame_technique",
    "blunders_per_100": "blunder_check",
    "mistakes_per_100": "blunder_check",
    "misses_per_100": "tactical_vision",
    "conversion": "converting_advantage",
    "resilience": "defense",
    "time_trouble_share": "time_management",
    "hasty_per_100": "time_management",
}


def lesson_for(kind: str, key: str) -> str | None:
    """Урок к сильной / слабой стороне: мотив — урок мотива, дебют — про репертуар."""
    if kind == "motif":
        return key if key in LESSONS else None
    if kind == "opening":
        return "opening_repertoire"
    return METRIC_LESSONS.get(key)
