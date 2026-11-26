"""Правила слабых мест (`app/insights/rules.py`) на фиксированных агрегатах."""

import math

import pytest

from app.db.models import Color
from app.insights.rules import (
    THRESHOLDS,
    Aggregates,
    ConversionAgg,
    MotifAgg,
    OpeningAgg,
    PhaseAgg,
    Stats,
    Thresholds,
    TimeAgg,
    Train,
    conversion_findings,
    find_weaknesses,
    motif_findings,
    opening_findings,
    phase_findings,
    time_findings,
    two_proportion_z,
)
from app.review.types import Phase

# Фон: мотивы, которые пользователь обычно не упускает (10 %).
BACKGROUND = [
    MotifAgg("hanging_piece", 100, 10),
    MotifAgg("mate_in_n", 50, 5),
    MotifAgg("pin", 50, 5),
]


def test_two_proportion_z() -> None:
    assert two_proportion_z(30, 100, 10, 100) == pytest.approx(3.54, abs=0.01)
    assert two_proportion_z(10, 100, 10, 100) == 0
    assert two_proportion_z(5, 100, 10, 100) < 0
    assert two_proportion_z(0, 0, 10, 100) == 0
    assert two_proportion_z(0, 10, 0, 10) == 0  # нулевая дисперсия


# --- Мотивы -----------------------------------------------------------------------------------


def test_motif_missed_more_often_than_others() -> None:
    [finding] = motif_findings([*BACKGROUND, MotifAgg("fork", 30, 12)])
    assert finding.kind == "motif"
    assert finding.key == "fork"
    assert finding.id == "motif:fork"
    # 12 из 30 возможностей (40 %) против 20 из 200 по остальным мотивам (10 %).
    assert finding.stats == Stats(value=40.0, baseline=10.0, count=12, total=30)
    assert finding.severity == "high"
    assert finding.train == Train(kind="puzzles", theme="fork")


def test_motif_like_others_is_not_a_weakness() -> None:
    assert motif_findings([*BACKGROUND, MotifAgg("fork", 30, 4)]) == []


def test_motif_needs_enough_opportunities_and_misses() -> None:
    # 3 из 6: доля высокая, но возможностей мало.
    assert motif_findings([*BACKGROUND, MotifAgg("fork", 6, 3)]) == []
    # 3 упущенных из 8 — меньше `motif_min_missed`.
    assert motif_findings([*BACKGROUND, MotifAgg("fork", 8, 3)]) == []


def test_motif_small_lift_with_big_sample_is_not_reported() -> None:
    # 12 % против 10 % на больших числах: статистически заметно, практически — нет.
    many = [MotifAgg("hanging_piece", 5000, 500), MotifAgg("fork", 5000, 600)]
    assert motif_findings(many) == []


def test_motif_only_one_motif_has_no_baseline() -> None:
    assert motif_findings([MotifAgg("fork", 30, 20)]) == []


def test_motif_top_limited_and_sorted() -> None:
    weak = [MotifAgg(f"m{i}", 30, 10 + i) for i in range(6)]
    findings = motif_findings([*BACKGROUND * 5, *weak])
    assert len(findings) == THRESHOLDS.motif_max_findings
    scores = [(f.severity, f.score) for f in findings]
    assert findings[0].key == "m5"
    assert scores == sorted(scores, key=lambda s: ({"high": 0, "medium": 1, "low": 2}[s[0]], -s[1]))


# --- Фазы -------------------------------------------------------------------------------------


def test_endgame_worse_than_middlegame() -> None:
    phases = [
        PhaseAgg(Phase.OPENING, 300, 3),
        PhaseAgg(Phase.MIDDLEGAME, 1000, 80),
        PhaseAgg(Phase.ENDGAME, 300, 60),
    ]
    [finding] = phase_findings(phases)
    assert finding.key == "endgame"
    # Сравнение — только с миттельшпилем: дебют почти весь книжный.
    assert finding.stats == Stats(value=20.0, baseline=8.0, count=60, total=300)
    assert finding.train == Train(kind="endgames")


def test_middlegame_not_compared_with_book_opening() -> None:
    # В дебюте ошибок нет, миттельшпиль и эндшпиль одинаковы — слабого места нет.
    phases = [
        PhaseAgg(Phase.OPENING, 500, 0),
        PhaseAgg(Phase.MIDDLEGAME, 1000, 100),
        PhaseAgg(Phase.ENDGAME, 300, 30),
    ]
    assert phase_findings(phases) == []


def test_opening_worse_than_rest() -> None:
    phases = [
        PhaseAgg(Phase.OPENING, 400, 60),
        PhaseAgg(Phase.MIDDLEGAME, 1000, 80),
        PhaseAgg(Phase.ENDGAME, 300, 24),
    ]
    [finding] = phase_findings(phases)
    assert finding.key == "opening"
    assert finding.stats.baseline == 8.0
    assert finding.train == Train(kind="puzzles", phase=Phase.OPENING)


def test_phase_needs_enough_moves() -> None:
    phases = [PhaseAgg(Phase.MIDDLEGAME, 1000, 80), PhaseAgg(Phase.ENDGAME, 100, 30)]
    assert phase_findings(phases) == []


# --- Время ------------------------------------------------------------------------------------


def test_time_trouble_errors() -> None:
    time = TimeAgg(
        trouble_moves=100,
        trouble_errors=25,
        calm_moves=1000,
        calm_errors=80,
        fast_moves=300,
        fast_errors=24,
    )
    [finding] = time_findings(time)
    assert finding.id == "time:trouble"
    assert finding.stats == Stats(value=25.0, baseline=8.0, count=25, total=100)
    assert finding.train == Train(kind="puzzles")


def test_hasty_errors() -> None:
    time = TimeAgg(
        trouble_moves=100,
        trouble_errors=8,
        calm_moves=1000,
        calm_errors=100,
        fast_moves=300,
        fast_errors=60,
    )
    [finding] = time_findings(time)
    assert finding.id == "time:hasty"
    # Быстрые ходы вне цейтнота (20 %) против остальных ходов вне цейтнота (40 из 700).
    assert finding.stats == Stats(value=20.0, baseline=5.7, count=60, total=300)


def test_fast_moves_with_fewer_errors_are_fine() -> None:
    # Быстрые ходы обычно очевидные — ошибок среди них меньше: это не поспешность.
    time = TimeAgg(
        trouble_moves=100,
        trouble_errors=9,
        calm_moves=1000,
        calm_errors=100,
        fast_moves=600,
        fast_errors=40,
    )
    assert time_findings(time) == []
    assert time_findings(None) == []


def test_time_needs_enough_moves() -> None:
    time = TimeAgg(
        trouble_moves=20,
        trouble_errors=10,
        calm_moves=1000,
        calm_errors=80,
        fast_moves=0,
        fast_errors=0,
    )
    assert time_findings(time) == []


# --- Дебюты -----------------------------------------------------------------------------------


def _openings(french_games: int, french_points: float) -> list[OpeningAgg]:
    return [
        OpeningAgg(Color.WHITE, "Italian Game", "C50", 60, 36.0),
        OpeningAgg(Color.WHITE, "Sicilian Defense", "B20", 60, 33.0),
        OpeningAgg(Color.WHITE, "French Defense", "C00", french_games, french_points),
        # Чёрными — свой счёт: плохие дебюты белыми не сравниваются с чёрными.
        OpeningAgg(Color.BLACK, "Italian Game", "C50", 60, 18.0),
        OpeningAgg(Color.BLACK, "Queen's Pawn Game", "D00", 40, 14.0),
    ]


def test_opening_with_bad_score() -> None:
    [finding] = opening_findings(_openings(30, 9.0))
    assert finding.key == "white:French Defense"
    # 30 % против 57.5 % в остальных дебютах белыми.
    assert finding.stats == Stats(value=30.0, baseline=57.5, count=30, total=150)
    assert finding.train == Train(kind="course", eco="C00")


def test_opening_with_normal_score() -> None:
    assert opening_findings(_openings(30, 15.0)) == []


def test_opening_needs_enough_games() -> None:
    assert opening_findings(_openings(8, 0.0)) == []


def test_opening_findings_limited() -> None:
    bad = [OpeningAgg(Color.WHITE, f"Bad {i}", None, 20, 2.0) for i in range(5)]
    good = [OpeningAgg(Color.WHITE, "Good", None, 200, 140.0)]
    assert len(opening_findings([*good, *bad])) == THRESHOLDS.opening_max_findings


# --- Реализация -------------------------------------------------------------------------------


def test_conversion_failures() -> None:
    [finding] = conversion_findings(
        ConversionAgg(games=30, points=18.0, expected_points=26.0, not_won=13)
    )
    assert finding.id == "conversion:winning"
    # Потеряно 40 % очков при ожидании ~13.3 %.
    assert finding.stats == Stats(value=40.0, baseline=13.3, count=13, total=30)
    assert finding.severity == "high"
    assert finding.train == Train(kind="endgames")


def test_conversion_as_expected() -> None:
    assert conversion_findings(ConversionAgg(30, 25.0, 26.0, 5)) == []
    assert conversion_findings(None) == []


def test_conversion_needs_enough_games() -> None:
    assert conversion_findings(ConversionAgg(5, 1.0, 4.5, 4)) == []


# --- Всё вместе -------------------------------------------------------------------------------


def _aggregates(analyzed: int) -> Aggregates:
    return Aggregates(
        analyzed_games=analyzed,
        motifs=[*BACKGROUND, MotifAgg("fork", 30, 12)],
        phases=[PhaseAgg(Phase.MIDDLEGAME, 1000, 80), PhaseAgg(Phase.ENDGAME, 300, 60)],
        openings=_openings(30, 9.0),
        conversion=ConversionAgg(30, 24.5, 26.0, 6),
    )


@pytest.mark.parametrize(
    ("analyzed", "expected"),
    [(THRESHOLDS.min_games - 1, 0), (THRESHOLDS.min_games, 3)],
)
def test_min_games_boundary(analyzed: int, expected: int) -> None:
    assert len(find_weaknesses(_aggregates(analyzed))) == expected


def test_sorted_by_severity_then_score() -> None:
    findings = find_weaknesses(_aggregates(50))
    order = {"high": 0, "medium": 1, "low": 2}
    keys = [(order[f.severity], -f.score) for f in findings]
    assert keys == sorted(keys)
    assert {f.kind for f in findings} == {"motif", "phase", "opening"}
    for f in findings:
        assert 0 <= f.score <= 100


def test_thresholds_are_configurable() -> None:
    strict = Thresholds(min_games=100)
    assert find_weaknesses(_aggregates(50), strict) == []
    lenient = Thresholds(motif_min_missed=1, motif_min_opportunities=1)
    assert [f.key for f in motif_findings([*BACKGROUND, MotifAgg("fork", 6, 3)], lenient)] == [
        "fork"
    ]


def test_infinite_lift_when_baseline_is_zero() -> None:
    [finding] = motif_findings([MotifAgg("pin", 100, 0), MotifAgg("fork", 20, 8)])
    assert finding.score <= 100
    assert not math.isnan(finding.score)
