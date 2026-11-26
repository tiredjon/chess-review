"""Правила забегов «Пазлы на время»: форма итога и правдоподобие счёта (без БД)."""

from datetime import timedelta

import pytest

from app.puzzles.rush import (
    MAX_MISTAKES,
    RunInvalidError,
    Variant,
    attempt_window,
    check_run_shape,
    check_score_plausible,
)


@pytest.mark.parametrize(
    ("variant", "mistakes", "duration_s"),
    [
        ("3min", 0, 180),
        ("3min", 3, 12),
        ("3min", 1, 185),  # итог уходит уже после сигнала таймера
        ("5min", 2, 300),
        ("survival", MAX_MISTAKES, 3000),
    ],
)
def test_valid_shape(variant: Variant, mistakes: int, duration_s: int) -> None:
    check_run_shape(variant, score=5, mistakes=mistakes, duration_s=duration_s)


@pytest.mark.parametrize(
    ("variant", "mistakes", "duration_s"),
    [
        ("3min", 4, 100),  # больше трёх ошибок
        ("3min", -1, 100),
        ("3min", 0, 200),  # дольше лимита
        ("5min", 0, 400),
        ("survival", 2, 100),  # выживание кончается только третьей ошибкой
        ("survival", 3, 4 * 3600),  # дольше трёх часов
    ],
)
def test_invalid_shape(variant: Variant, mistakes: int, duration_s: int) -> None:
    with pytest.raises(RunInvalidError):
        check_run_shape(variant, score=5, mistakes=mistakes, duration_s=duration_s)


def test_negative_score() -> None:
    with pytest.raises(RunInvalidError):
        check_run_shape("3min", score=-1, mistakes=0, duration_s=60)


def test_score_plausibility() -> None:
    check_score_plausible(0, 0)
    check_score_plausible(7, 7)
    check_score_plausible(3, 7)  # часть решённых клиент мог не засчитать
    with pytest.raises(RunInvalidError):
        check_score_plausible(8, 7)


def test_attempt_window_is_duration_plus_a_minute() -> None:
    assert attempt_window(180) == timedelta(seconds=240)
