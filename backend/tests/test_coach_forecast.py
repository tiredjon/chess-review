"""Прогноз тренера (17.2): чистая функция на синтетических траекториях."""

from datetime import date, timedelta
from typing import Any

import pytest

from app.coach.forecast import (
    ForecastInput,
    RatingWeek,
    Reference,
    forecast,
    weighted_trend,
)
from app.coach.norms_data import parse_trajectories

TODAY = date(2026, 11, 27)


def row(
    gain: int,
    *,
    r52: float = 0.3,
    r104: float = 0.55,
    r156: float = 0.7,
    weeks: tuple[float, float, float] | None = (30, 60, 100),
    players: int = 80,
    activity: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "from_center": 1700,
        "gain": gain,
        "players": players,
        "reached_52w": r52,
        "reached_104w": r104,
        "reached_156w": r156,
        "weeks_p25": weeks[0] if weeks else None,
        "weeks_p50": weeks[1] if weeks else None,
        "weeks_p75": weeks[2] if weeks else None,
        "activity": activity or [],
    }


def trajectories(*rows: dict[str, Any], version: str = "2026-11") -> Any:
    return parse_trajectories(
        {"version": version, "source": "chesscom", "time_classes": {"rapid": {"rows": list(rows)}}}
    )


TR = trajectories(
    row(100, r52=0.6, r104=0.8, r156=0.9, weeks=(8, 20, 40)),
    row(300, r156=0.85),
    row(600, r52=0.05, r104=0.15, r156=0.25, weeks=(70, 100, 130)),
)


def history(slope: float, weeks: int = 12, games: int = 5, start: int = 1700) -> list[RatingWeek]:
    return [
        RatingWeek(
            week=TODAY - timedelta(weeks=weeks - i),
            rating=round(start + slope * i),
            games=games,
        )
        for i in range(weeks + 1)
    ]


def inp(**kw: Any) -> ForecastInput:
    base: dict[str, Any] = {
        "today": TODAY,
        "time_class": "rapid",
        "start_rating": 1700,
        "current_rating": 1700,
        "target_rating": 2000,
        "history": [],
        "user_games": 60,
        "games_per_week": 5.0,
        "adherence": None,
        "plan_weeks": 0,
    }
    base.update(kw)
    return ForecastInput(**base)


def test_weighted_trend() -> None:
    slope, se, n = weighted_trend(history(5.0), TODAY) or (0, 0, 0)
    assert slope == pytest.approx(5.0, abs=0.1)
    assert se >= 2.0
    assert n == 65
    assert weighted_trend(history(5.0, weeks=1), TODAY) is None
    # Старые недели (> 12) не учитываются.
    old = [RatingWeek(TODAY - timedelta(weeks=30 + i), 1000 + i * 50, 3) for i in range(4)]
    assert weighted_trend(old, TODAY) is None


def test_base_curve_is_a_range() -> None:
    f = forecast(inp(), TR)
    assert f.status == "on_track"
    assert f.weeks_p50 is not None
    assert f.weeks_p80 is not None
    assert 40 <= f.weeks_p50 < f.weeks_p80 <= 156
    assert f.date_p50 == TODAY + timedelta(weeks=f.weeks_p50)
    assert f.reach_probability_1y == pytest.approx(0.3, abs=0.02)
    assert f.basis.sample_players == 80
    assert f.confidence == "medium"
    # Коридор до p80: p10 ≤ p50 ≤ p90, расширяется, p50 доходит до цели к p50.
    assert f.projection[0].p50 == 1700
    assert len(f.projection) == f.weeks_p80 + 1
    assert all(p.p10 <= p.p50 <= p.p90 for p in f.projection)
    width = [p.p90 - p.p10 for p in f.projection]
    assert width == sorted(width)
    assert f.projection[f.weeks_p50].p50 == pytest.approx(2000, abs=1)


def test_hard_goal_has_no_dates() -> None:
    f = forecast(inp(target_rating=2300), TR)
    assert f.weeks_p50 is None
    assert f.date_p50 is None
    assert f.date_p80 is None
    assert f.reach_probability_1y is not None
    assert f.reach_probability_1y < 0.1
    # Коридор — на 3 года.
    assert len(f.projection) == 157
    assert f.projection[-1].p50 < 2300


def test_own_trend_and_adherence_shift_the_curve() -> None:
    base = forecast(inp(), TR)
    fast = forecast(inp(history=history(10.0, games=10)), TR)
    flat = forecast(inp(history=history(-3.0, games=10)), TR)
    lazy = forecast(inp(adherence=0.0), TR)
    diligent = forecast(inp(adherence=1.0), TR)
    assert base.weeks_p50
    assert fast.weeks_p50
    assert lazy.weeks_p50
    assert diligent.weeks_p50
    assert fast.weeks_p50 < base.weeks_p50
    assert flat.weeks_p50 is None or flat.weeks_p50 > base.weeks_p50
    assert fast.basis.weekly_trend == pytest.approx(10.0, abs=0.2)
    assert lazy.weeks_p50 > diligent.weeks_p50 == base.weeks_p50


def test_activity_bucket() -> None:
    tr = trajectories(
        row(
            300,
            activity=[
                {
                    "games_per_week_lo": 0,
                    "games_per_week_hi": 3,
                    "players": 30,
                    "reached_104w": 0.3,
                    "weeks_p50": 90,
                },
                {
                    "games_per_week_lo": 3,
                    "games_per_week_hi": 100,
                    "players": 50,
                    "reached_104w": 0.7,
                    "weeks_p50": 45,
                },
            ],
        )
    )
    rare = forecast(inp(games_per_week=1.0), tr)
    often = forecast(inp(games_per_week=8.0), tr)
    assert rare.basis.sample_players == 30
    assert often.basis.sample_players == 50
    assert often.weeks_p50 is not None
    assert rare.weeks_p50 is None or rare.weeks_p50 > often.weeks_p50


def test_achieved() -> None:
    f = forecast(inp(current_rating=2010), TR)
    assert f.status == "achieved"
    assert f.weeks_p50 == 0
    assert f.date_p50 == TODAY
    assert f.reach_probability_1y == 1.0
    assert f.projection == []


def test_placeholder_is_low_confidence() -> None:
    placeholder = trajectories(version="placeholder")
    # Мало данных — insufficient, без дат.
    f = forecast(inp(user_games=10, history=history(5.0)), placeholder)
    assert f.status == "insufficient"
    assert f.confidence == "low"
    assert f.weeks_p50 is None
    assert f.projection == []
    assert f.reach_probability_1y is None
    # Достаточно своих партий и тренд — прогноз по тренду, но уверенность низкая.
    g = forecast(inp(user_games=80, history=history(6.0, games=8)), placeholder)
    assert g.status != "insufficient"
    assert g.confidence == "low"
    assert g.weeks_p50 is not None
    assert 35 <= g.weeks_p50 <= 70
    # Отрицательный тренд — цель за 3 года не достигается.
    h = forecast(inp(user_games=80, history=history(-2.0, games=8)), placeholder)
    assert h.weeks_p50 is None
    assert h.date_p80 is None


def test_confidence_levels() -> None:
    assert forecast(inp(user_games=20), TR).confidence == "low"
    assert forecast(inp(user_games=120, plan_weeks=2), TR).confidence == "medium"
    assert forecast(inp(user_games=120, plan_weeks=4), TR).confidence == "high"


@pytest.mark.parametrize(
    ("current", "status"), [(1850, "ahead"), (1800, "on_track"), (1740, "behind")]
)
def test_status_against_reference(current: int, status: str) -> None:
    # Опорная p50-линия: 1700 → 2000 за 30 недель; прошло 10 недель — ожидается 1800.
    ref = Reference(
        day=TODAY - timedelta(weeks=10), rating=1700, date_p50=TODAY + timedelta(weeks=20)
    )
    f = forecast(inp(current_rating=current, reference=ref), TR)
    assert f.status == status


def test_insufficient_without_rows_for_time_class() -> None:
    f = forecast(inp(time_class="blitz", user_games=5), TR)
    assert f.status == "insufficient"
    assert f.history == []
