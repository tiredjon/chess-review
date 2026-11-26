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
from app.review.game_rating import TimeClass, expected_accuracy, game_rating, time_class
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


def test_game_rating_at_expected_accuracy_is_own_rating() -> None:
    # Сыграл ровно как в среднем играет его рейтинг — рейтинг партии и есть его рейтинг.
    for rating in (600, 1200, 1800, 2400):
        for tc in ("rapid", "blitz", "bullet"):
            estimate = game_rating(expected_accuracy(rating, tc), tc, rating=rating)
            assert estimate == pytest.approx(rating, abs=50)


def test_game_rating_is_monotonic_and_clamped() -> None:
    for rating in (None, 500, 1500, 2500):
        ratings = [game_rating(acc, rating=rating) for acc in range(10, 100, 5)]
        assert ratings == sorted(ratings)
        assert ratings[0] >= 100
        assert ratings[-1] <= 3200
        assert all(value % 50 == 0 for value in ratings)


# Настоящие Game Rating из разборов Chess.com (скриншоты пользователя, 2026-11; рейтинги и
# контроль — из публичного API): точность, рейтинг игрока, рейтинг соперника, контроль, Game
# Rating. По ним подобраны NOISE и TAU.
CHESSCOM_GAME_RATINGS: list[tuple[float, int, int, TimeClass, int]] = [
    (93.99, 1727, 1718, "rapid", 2350),
    (63.9, 1718, 1727, "rapid", 1200),
    (75.5, 1714, 1727, "rapid", 1350),
    (86.77, 1727, 1714, "rapid", 2200),
    (96.27, 1764, 1767, "rapid", 2400),
    (85.2, 1767, 1764, "rapid", 2150),
    (77.23, 1750, 1750, "rapid", 1750),
    (71.37, 1750, 1750, "rapid", 1250),
    (68.79, 1181, 1151, "blitz", 900),
    (69.82, 1151, 1181, "blitz", 1000),
    (51.15, 1191, 1186, "blitz", 450),
    (62.26, 1186, 1191, "blitz", 700),
    (64.8, 1176, 1199, "blitz", 800),
    (83.59, 1199, 1176, "blitz", 1750),
    (69.11, 1070, 1077, "bullet", 1050),
    (68.69, 1077, 1070, "bullet", 1000),
    (60.59, 1069, 1034, "bullet", 600),
    (55.16, 1034, 1069, "bullet", 450),
]


def test_game_rating_matches_chesscom() -> None:
    errors = [
        game_rating(accuracy, tc, rating=rating, opponent_rating=opponent) - expected
        for accuracy, rating, opponent, tc, expected in CHESSCOM_GAME_RATINGS
    ]
    # У Chess.com в оценке ещё и каждый ход, так что точного совпадения нет; но в среднем —
    # меньше двух шагов округления, без смещения и без промахов больше чем на 300.
    assert sum(abs(error) for error in errors) / len(errors) <= 80
    assert abs(sum(errors) / len(errors)) <= 30
    assert max(abs(error) for error in errors) <= 300


@pytest.mark.parametrize(
    ("accuracy", "tc", "rating", "low", "high"),
    [
        # Раньше — 2100: обращение пологой кривой «в лоб».
        (79.7, "blitz", 463, 700, 1400),
        # Раньше — 3200 у обоих игроков пули ~1000.
        (94.9, "bullet", 1016, 1500, 2400),
        (84.6, "bullet", 1051, 1100, 1800),
        # Раньше — 2850.
        (92.2, "rapid", 1724, 2200, 2700),
        # Слабая партия сильного игрока — ниже его рейтинга, но не «новичок».
        (75.0, "blitz", 2400, 1800, 2300),
    ],
)
def test_game_rating_stays_near_player_rating(
    accuracy: float, tc: TimeClass, rating: int, low: int, high: int
) -> None:
    assert low <= game_rating(accuracy, tc, rating=rating) <= high


def test_game_rating_falls_back_to_opponent_and_population() -> None:
    # Без своего рейтинга опора — соперник, без обоих — средний игрок: оценка всё равно
    # не улетает к краям шкалы.
    assert game_rating(79.7, "blitz", opponent_rating=460) < game_rating(79.7, "blitz")
    assert 1000 <= game_rating(95.0, "bullet") <= 2600
    assert 100 < game_rating(40.0, "rapid") < 900


PARAMS_LICHESS = CcParams(k=0.00368208, b=0.04354, c=3.1669, p=1.0)
