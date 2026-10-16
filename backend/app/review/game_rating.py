"""Рейтинг партии по точности — как «Game Rating» в разборе Chess.com.

Модель — ожидаемая точность игрока рейтинга r на Chess.com, своя кривая на контроль времени:
  E[точность | r] = a − b·e^(−r/c)   (daily — кривая рапида + DAILY_SHIFT),
подобрана по публичным архивам Chess.com (`scripts/collect_chesscom_accuracy.py`,
`scripts/fit_game_rating.py`). Рейтинг партии — обратная функция: какой рейтинг в среднем
играет с такой точностью.
"""

import math
import re
from typing import Literal

TimeClass = Literal["bullet", "blitz", "rapid", "daily"]

# Подобраны scripts/fit_game_rating.py по 20 500 парам (см. SPEC «Принятые решения»).
CURVES: dict[TimeClass, tuple[float, float, float]] = {
    "rapid": (110.0, 66.1554, 2370.91),
    "blitz": (98.854, 37.612, 2995.78),
    "bullet": (101.627, 35.9917, 6000.0),
}
DAILY_SHIFT = 12.286
MIN_RATING, MAX_RATING = 100, 3200
# Округление, как у Chess.com (1750, 1250).
STEP = 50

_TIME_CONTROL_RE = re.compile(r"^(\d+)(?:\+(\d+))?$")


def time_class(time_control: str | None) -> TimeClass:
    """Контроль времени из PGN → класс Chess.com: ожидаемая длительность = база + 40·добавка;
    < 3 мин — bullet, < 10 — blitz, иначе rapid; `1/N` — daily. Неизвестный — rapid."""
    if time_control and time_control.startswith("1/"):
        return "daily"
    match = _TIME_CONTROL_RE.match(time_control or "")
    if match is None:
        return "rapid"
    total = int(match[1]) + 40 * int(match[2] or 0)
    if total < 180:
        return "bullet"
    if total < 600:
        return "blitz"
    return "rapid"


def _curve(time_control: TimeClass) -> tuple[float, float, float]:
    if time_control == "daily":
        a, b, c = CURVES["rapid"]
        return a + DAILY_SHIFT, b, c
    return CURVES[time_control]


def expected_accuracy(rating: float, time_control: TimeClass = "rapid") -> float:
    a, b, c = _curve(time_control)
    return a - b * math.exp(-rating / c)


def group_accuracy(rating: int | None, time_control: str | None) -> float | None:
    """Средняя точность игроков этого рейтинга и контроля (рейтинговая группа, сессия 11).
    Рейтинг — Chess.com: кривые подобраны по их пулу (у Lichess шкала другая)."""
    if rating is None:
        return None
    return round(expected_accuracy(rating, time_class(time_control)), 1)


def game_rating(accuracy: float, time_control: TimeClass = "rapid") -> int:
    """Рейтинг, который в среднем играет с такой точностью, с шагом STEP."""
    a, b, c = _curve(time_control)
    gap = a - accuracy
    rating = MAX_RATING if gap <= 0 else -c * math.log(gap / b)
    rating = max(MIN_RATING, min(MAX_RATING, rating))
    return int(round(rating / STEP) * STEP)
