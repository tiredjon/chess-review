"""Забеги «Пазлы на время» (сессия 16.2): варианты и проверка правдоподобия результата.

Забег идёт на клиенте (таймер, счёт, ошибки), сервер видит только попытки `mode=rush`, которые
клиент отправлял по ходу забега. Итог принимается, если счёт не больше верных попыток за время
забега плюс минута запаса (сеть, повторная отправка), и не вылезает за рамки варианта.
"""

from datetime import timedelta
from typing import Literal

Variant = Literal["3min", "5min", "survival"]

MAX_MISTAKES = 3
# Запас к длительности забега при подсчёте попыток; клиентские часы и сеть не точны.
ATTEMPT_WINDOW_SLACK = timedelta(seconds=60)
# Допуск к лимиту времени: итог отправляется уже после сигнала таймера.
DURATION_SLACK_S = 10
# Лимит времени варианта в секундах; None — без времени («на выживание»).
TIME_LIMITS: dict[Variant, int | None] = {"3min": 180, "5min": 300, "survival": None}
# Забег на выживание длиннее трёх часов — это уже не забег.
MAX_DURATION_S = 3 * 3600


class RunInvalidError(ValueError):
    """Итог забега не бывает: счёт, ошибки или длительность вне допустимого."""


def attempt_window(duration_s: int) -> timedelta:
    """За какое время до сохранения итога искать попытки этого забега."""
    return timedelta(seconds=duration_s) + ATTEMPT_WINDOW_SLACK


def check_run_shape(variant: Variant, *, score: int, mistakes: int, duration_s: int) -> None:
    """Проверка без БД: форма итога по правилам варианта."""
    if not 0 <= mistakes <= MAX_MISTAKES:
        raise RunInvalidError(f"ошибок не больше {MAX_MISTAKES}")
    limit = TIME_LIMITS[variant]
    if limit is not None and duration_s > limit + DURATION_SLACK_S:
        raise RunInvalidError("забег длиннее лимита варианта")
    if duration_s > MAX_DURATION_S:
        raise RunInvalidError("забег слишком длинный")
    if limit is None and mistakes < MAX_MISTAKES:
        # «На выживание» кончается только на третьей ошибке.
        raise RunInvalidError("забег на выживание заканчивается третьей ошибкой")
    if score < 0:
        raise RunInvalidError("счёт не может быть отрицательным")


def check_score_plausible(score: int, correct_attempts: int) -> None:
    """Счёт не больше верных rush-попыток в окне забега."""
    if score > correct_attempts:
        raise RunInvalidError("счёт больше числа решённых пазлов")
