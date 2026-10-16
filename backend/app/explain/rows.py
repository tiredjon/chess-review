"""Данные для общего разбора из строк `games` / `analyses` (API и Telegram-бот)."""

from typing import Any

from app.db.accuracy import pick_accuracy
from app.db.models import Analysis, Color, Game
from app.explain.facts import GameInfo


def _accuracy(game: Game, analysis: Analysis, color: Color) -> float | None:
    picked = pick_accuracy(game, analysis, color)
    return None if picked is None else picked[0]


def game_info(game: Game, analysis: Analysis, *, user_color: Color | None) -> GameInfo:
    """Сводка партии для `Explainer.summarize`. Точность — та же, что на плашках
    (`app/db/accuracy.py`); `user_color` — для кого пишется разбор (None — для обоих)."""
    phase_accuracy: Any = analysis.phase_accuracy
    return GameInfo(
        white=game.white,
        black=game.black,
        white_elo=game.white_elo,
        black_elo=game.black_elo,
        result=game.result,
        opening_name=game.opening_name,
        user_color=user_color.value if user_color else None,
        white_accuracy=_accuracy(game, analysis, Color.WHITE),
        black_accuracy=_accuracy(game, analysis, Color.BLACK),
        phase_accuracy=phase_accuracy,
    )
