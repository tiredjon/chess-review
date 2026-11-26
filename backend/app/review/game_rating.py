"""Рейтинг партии по точности — как «Game Rating» в разборе Chess.com.

Две части.

1. Ожидаемая точность игрока рейтинга r на Chess.com, своя кривая на контроль времени:
     E[точность | r] = a − b·e^(−r/c)   (daily — кривая рапида + DAILY_SHIFT),
   подобрана по публичным архивам Chess.com (`scripts/collect_chesscom_accuracy.py`,
   `scripts/fit_game_rating.py`). На ней же — средняя точность рейтинговой группы.

2. Рейтинг партии — не обратная функция кривой «в лоб» (кривая пологая, и шум точности в
   одной партии, ±8–10 пунктов, превращался в ±1000 Elo: 79.7 % в блице у игрока 460 давало
   2000, 95 % в пуле — 3200). Это оценка по Байесу, как у Chess.com («качество ходов против
   ожидаемого от игрока вашего рейтинга»):
     — априори сыгранный уровень ~ N(рейтинг игрока, TAU²) — у Chess.com рейтинг игроков
       тоже входит в расчёт; без рейтинга — рейтинг соперника (шире), без обоих — средний
       игрок Chess.com (ещё шире);
     — правдоподобие: точность ~ N(E[точность | уровень], σ²), σ — шум точности в одной
       партии сверх разницы в уровне игры (подобран по разбросу точности игроков одного
       рейтинга, `NOISE`);
     — ответ — медиана апостериорного распределения на сетке рейтингов, с шагом STEP.
"""

import math
import re
from typing import Literal

TimeClass = Literal["bullet", "blitz", "rapid", "daily"]

# Подобраны scripts/fit_game_rating.py (см. SPEC «Принятые решения»).
CURVES: dict[TimeClass, tuple[float, float, float]] = {
    "rapid": (110.0, 66.1554, 2370.91),
    "blitz": (98.854, 37.612, 2995.78),
    "bullet": (101.627, 35.9917, 6000.0),
}
DAILY_SHIFT = 12.286
# Шум точности одной партии (σ, пункты) при одном и том же уровне игры, и разброс сыгранного
# уровня вокруг рейтинга игрока (TAU, Elo); вокруг рейтинга соперника — шире (соперники обычно
# близки по силе, но не всегда); без рейтингов — средний игрок Chess.com.
# Подобраны перебором по 18 настоящим Game Rating из разборов Chess.com (рапид ~1750, блиц
# ~1180, пуля ~1060; точность 51–96 %, `tests/test_cc_accuracy.py::CHESSCOM_GAME_RATINGS`):
# средняя ошибка 72 Elo при шаге округления 50, смещения нет. Значения лежат на пологом гребне
# (σ/TAU ≈ 1/100): соседние дают 70–80, так что это не подгонка под шум. Разброс точности
# игроков одного рейтинга по сбору 2026-11 — 9–17 пунктов; σ меньше, потому что разница в
# уровне игры уже в TAU.
NOISE: dict[TimeClass, float] = {"rapid": 7.0, "daily": 7.0, "blitz": 7.0, "bullet": 6.0}
TAU = 700.0
TAU_OPPONENT = 850.0
POPULATION = (1200.0, 800.0)
MIN_RATING, MAX_RATING = 100, 3200
# Сетка апостериорного распределения.
GRID_STEP = 10
# Округление, как у Chess.com (1750, 1250).
STEP = 50

_TIME_CONTROL_RE = re.compile(r"^(\d+)(?:\+(\d+))?$")
_GRID = tuple(range(MIN_RATING, MAX_RATING + 1, GRID_STEP))


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


def _prior(rating: int | None, opponent_rating: int | None) -> tuple[float, float]:
    if rating is not None:
        return float(rating), TAU
    if opponent_rating is not None:
        return float(opponent_rating), TAU_OPPONENT
    return POPULATION


def _posterior_median(
    accuracy: float, time_control: TimeClass, mean: float, spread: float
) -> float:
    """Медиана апостериорного распределения уровня игры на сетке рейтингов (без округления).
    Медиана, а не мода: мода у краёв шкалы липнет к 100 / 3200."""
    noise = NOISE[time_control]
    a, b, c = _curve(time_control)
    logs = [
        -(((accuracy - (a - b * math.exp(-r / c))) / noise) ** 2) / 2
        - (((r - mean) / spread) ** 2) / 2
        for r in _GRID
    ]
    top = max(logs)
    weights = [math.exp(value - top) for value in logs]
    half, total = sum(weights) / 2, 0.0
    for r, weight in zip(_GRID, weights, strict=True):
        total += weight
        if total >= half:
            return float(r)
    return float(_GRID[-1])


def game_rating(
    accuracy: float,
    time_control: TimeClass = "rapid",
    *,
    rating: int | None = None,
    opponent_rating: int | None = None,
) -> int:
    """Уровень, на котором сыграна партия, с шагом STEP: медиана апостериорного распределения
    по точности `accuracy` при рейтинге игрока `rating` (или соперника) — см. docstring модуля.
    Рейтинги — шкала Chess.com."""
    mean, spread = _prior(rating, opponent_rating)
    estimate = _posterior_median(accuracy, time_control, mean, spread)
    # Кривая выпуклая, и апостериорное распределение несимметрично: партия, сыгранная ровно
    # на ожидаемую точность, давала бы не опорный рейтинг. Сдвиг убирает это смещение.
    expected = expected_accuracy(mean, time_control)
    estimate -= _posterior_median(expected, time_control, mean, spread) - mean
    estimate = max(MIN_RATING, min(MAX_RATING, estimate))
    return int(round(estimate / STEP) * STEP)
