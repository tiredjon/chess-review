import pytest
from chess.engine import Cp, Mate, MateGiven, Score

from app.review.winprob import format_score, score_to_cp, win_percent, win_percent_from_cp


@pytest.mark.parametrize(
    ("cp", "expected"),
    [
        (0, 50.0),
        (100, 59.10258971916128),
        (-100, 40.89741028083871),
        (300, 75.11255009383484),
        (1000, 97.54474363414323),
    ],
)
def test_win_percent_reference_values(cp: int, expected: float) -> None:
    assert win_percent_from_cp(cp) == pytest.approx(expected, abs=1e-9)


def test_win_percent_clamps_cp_to_1000() -> None:
    assert win_percent_from_cp(5000) == win_percent_from_cp(1000)
    assert win_percent_from_cp(-5000) == win_percent_from_cp(-1000)


@pytest.mark.parametrize("cp", [0, 35, 120, 480, 999, 2500])
def test_win_percent_is_symmetric(cp: int) -> None:
    assert win_percent_from_cp(cp) + win_percent_from_cp(-cp) == pytest.approx(100)


def test_win_percent_is_monotonic() -> None:
    values = [win_percent_from_cp(cp) for cp in range(-1200, 1201, 50)]

    assert values == sorted(values)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (Cp(42), 42),
        (Cp(-310), -310),
        (Mate(1), 9990),
        (Mate(5), 9950),
        (Mate(-1), -9990),
        (Mate(-5), -9950),
        (MateGiven, 10_000),
        (Mate(0), -10_000),
    ],
)
def test_score_to_cp_maps_mates(score: Score, expected: int) -> None:
    assert score_to_cp(score) == expected


def test_mate_scores_give_extreme_win_percent() -> None:
    assert win_percent(Mate(3)) == win_percent_from_cp(1000)
    assert win_percent(Mate(-3)) == win_percent_from_cp(-1000)
    assert win_percent(MateGiven) == win_percent_from_cp(1000)
    assert win_percent(Mate(0)) == win_percent_from_cp(-1000)


def test_negation_flips_point_of_view() -> None:
    assert win_percent(-Cp(150)) == pytest.approx(100 - win_percent(Cp(150)))
    assert -Mate(0) == MateGiven


@pytest.mark.parametrize(
    ("score", "text"),
    [
        (Cp(80), "+0.80"),
        (Cp(-320), "-3.20"),
        (Cp(0), "+0.00"),
        (Mate(3), "#3"),
        (Mate(-2), "#-2"),
        (Mate(0), "#"),
        (MateGiven, "#"),
    ],
)
def test_format_score(score: Score, text: str) -> None:
    assert format_score(score) == text
