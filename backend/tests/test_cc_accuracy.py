"""Точность «как у Chess.com» (`cc_accuracy.py`) и рейтинг партии (`game_rating.py`)."""

import chess.engine
import pytest

from app.review.cc_accuracy import (
    CP_CAP,
    CcParams,
    color_accuracy,
    game_accuracy,
    move_accuracy,
    score_cp,
    to_cp,
)
from app.review.game_rating import expected_accuracy, game_rating, time_class
from app.review.winprob import win_percent_from_cp


def test_perfect_moves_are_100() -> None:
    assert game_accuracy([(30, 30), (25, 40), (-50, -50)]) == pytest.approx(100)
    assert game_accuracy([]) == 100


def test_bigger_loss_lowers_accuracy() -> None:
    small, big = move_accuracy(50, 0, PARAMS_LICHESS), move_accuracy(50, -300, PARAMS_LICHESS)
    assert 0 <= big < small < 100


def test_lichess_shape_reproduces_lichess_move_accuracy() -> None:
    # С параметрами Lichess формула хода совпадает с review/accuracy.py.
    before, after = 0, -120
    delta = win_percent_from_cp(before) - win_percent_from_cp(after)
    expected = 103.1668 * 2.718281828 ** (-0.04354 * delta) - 3.1669
    assert move_accuracy(before, after, PARAMS_LICHESS) == pytest.approx(expected, abs=0.05)


def test_power_mean_punishes_blunders_more_with_lower_p() -> None:
    moves = [(0, 0)] * 9 + [(0, -900)]
    mean = game_accuracy(moves, CcParams(k=0.00368208, b=0.04354, c=3.1669, p=1.0))
    harmonic = game_accuracy(moves, CcParams(k=0.00368208, b=0.04354, c=3.1669, p=-1.0))
    geometric = game_accuracy(moves, CcParams(k=0.00368208, b=0.04354, c=3.1669, p=0.0))
    assert harmonic < geometric < mean < 100


def test_mate_scores() -> None:
    assert to_cp(None, 0) == CP_CAP  # ходящий поставил мат
    assert to_cp(None, 3) == CP_CAP
    assert to_cp(None, -2) == -CP_CAP
    assert to_cp(5000, None) == CP_CAP
    assert score_cp(chess.engine.Cp(-40)) == -40
    assert score_cp(chess.engine.Mate(-1)) == -CP_CAP
    assert score_cp(chess.engine.MateGiven) == CP_CAP


def test_color_accuracy_splits_by_side() -> None:
    rows = [
        (True, 20, None, 20, None),
        (False, -20, None, -500, None),
        (True, 480, None, 470, None),
    ]
    assert color_accuracy(rows, white=True) == pytest.approx(game_accuracy([(20, 20), (480, 470)]))
    assert color_accuracy(rows, white=False) == pytest.approx(game_accuracy([(-20, -500)]))
    assert color_accuracy(rows[:1], white=False) is None


@pytest.mark.parametrize(
    ("time_control", "expected"),
    [
        ("60", "bullet"),
        ("120+1", "bullet"),
        ("180", "blitz"),
        ("180+2", "blitz"),
        ("300+5", "blitz"),
        ("600", "rapid"),
        ("900+10", "rapid"),
        ("1/86400", "daily"),
        (None, "rapid"),
        ("-", "rapid"),
    ],
)
def test_time_class(time_control: str | None, expected: str) -> None:
    assert time_class(time_control) == expected


def test_game_rating_inverts_expected_accuracy() -> None:
    for rating in (600, 1200, 1800, 2400):
        for tc in ("rapid", "blitz", "bullet"):
            assert game_rating(expected_accuracy(rating, tc), tc) == pytest.approx(rating, abs=25)


def test_game_rating_is_monotonic_and_clamped() -> None:
    ratings = [game_rating(acc) for acc in range(10, 100, 5)]
    assert ratings == sorted(ratings)
    assert ratings[0] >= 100
    assert ratings[-1] <= 3200
    assert all(rating % 50 == 0 for rating in ratings)


def test_game_rating_matches_chesscom_example() -> None:
    # Партия из обратной связи пользователя: Chess.com — 77.23 → 1750, 71.37 → 1250 (рапид).
    assert game_rating(77.23, "rapid") == pytest.approx(1750, abs=100)
    assert game_rating(71.37, "rapid") == pytest.approx(1250, abs=150)


PARAMS_LICHESS = CcParams(k=0.00368208, b=0.04354, c=3.1669, p=1.0)
