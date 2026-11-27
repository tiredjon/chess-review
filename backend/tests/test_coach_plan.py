"""Планировщик тренера (17.2): чистая функция «слабые стороны + цель + тренировки → неделя»."""

from collections import Counter
from datetime import date, timedelta

import pytest

from app.api.schemas_coach import GapOut
from app.api.schemas_insights import TrainOut, TrainQueryOut
from app.coach.planner import (
    Availability,
    PlanGoal,
    TimeClassName,
    build_week_plan,
    study_days,
    study_weekdays,
    week_start_of,
)

MONDAY = date(2026, 11, 23)


def gap(
    key: str,
    score: float,
    *,
    kind: str = "motif",
    train: str | None = "puzzles",
    available: int = 30,
    theme: str | None = None,
    phase: str | None = None,
    eco: str | None = None,
    lesson: str | None = None,
) -> GapOut:
    return GapOut.model_validate(
        {
            "kind": kind,
            "key": key,
            "severity": "high",
            "score": score,
            "value": 1.0,
            "target_p50": 0.5,
            "train": None
            if train is None
            else TrainOut(
                kind=train,
                query=TrainQueryOut(theme=theme, phase=phase, eco=eco),
                available=available,
            ),
            "lesson": lesson,
            "examples": [],
        }
    )


def goal(
    minutes: int = 45, days: int = 5, target: int = 2000, tc: TimeClassName = "rapid"
) -> PlanGoal:
    return PlanGoal(
        time_class=tc, target_rating=target, minutes_per_day=minutes, days_per_week=days
    )


AVAIL = Availability(puzzles=200, courses_by_eco={"B90": "course-1"}, bot_elo=1700)

WEAK = [
    gap("fork", 80, theme="fork", lesson="fork"),
    gap("accuracy_endgame", 60, kind="metric", train="endgames", lesson="endgame_technique"),
    gap("time_trouble_share", 40, kind="metric", train="puzzles", lesson="time_management"),
    gap("pin", 10, theme="pin", lesson="pin"),
]


def kind_minutes(plan_tasks: object) -> Counter[str]:
    c: Counter[str] = Counter()
    for t in plan_tasks:  # type: ignore[attr-defined]
        c[t.kind] += t.minutes
    return c


def test_study_days_spread_from_monday() -> None:
    assert study_weekdays(5) == (0, 1, 2, 4, 5)
    assert study_weekdays(3) == (0, 2, 4)
    assert study_weekdays(1) == (0,)
    assert study_weekdays(7) == tuple(range(7))
    assert week_start_of(date(2026, 11, 29)) == MONDAY
    # С четверга — только оставшиеся учебные дни.
    assert study_days(MONDAY, 5, MONDAY + timedelta(days=3)) == (
        MONDAY + timedelta(days=4),
        MONDAY + timedelta(days=5),
    )
    # Воскресенье без учебных дней — учебным становится сегодня.
    sunday = MONDAY + timedelta(days=6)
    assert study_days(MONDAY, 5, sunday) == (sunday,)


def test_plan_is_deterministic() -> None:
    a = build_week_plan(WEAK, goal(), AVAIL, MONDAY, MONDAY)
    b = build_week_plan(list(reversed(WEAK)), goal(), AVAIL, MONDAY, MONDAY)
    assert a == b


@pytest.mark.parametrize("minutes", [20, 30, 45, 60, 90, 120])
@pytest.mark.parametrize("tc", ["blitz", "rapid", "bullet"])
def test_shares_and_daily_budget(minutes: int, tc: TimeClassName) -> None:
    plan = build_week_plan(WEAK, goal(minutes=minutes, tc=tc), AVAIL, MONDAY, MONDAY)
    assert len(plan.study_days) == 5
    total = sum(t.minutes for t in plan.tasks)
    by_kind = kind_minutes(plan.tasks)
    # Тактика ≥ 30 % (цель ≤ 2200), партия + разбор ≥ 25 %.
    assert (by_kind["puzzles"] + by_kind["rush"]) / total >= 0.30 - 0.03
    assert (by_kind["play"] + by_kind["review"]) / total >= 0.25 - 0.02
    game = {"bullet": 3, "blitz": 10, "rapid": 25}[tc]
    for d in plan.study_days:
        day_tasks = [t for t in plan.tasks if t.day == d]
        assert day_tasks
        spent = sum(t.minutes for t in day_tasks)
        has_long_game = any(t.kind == "play" and t.minutes > minutes for t in day_tasks)
        if not has_long_game and game + 10 <= minutes:
            assert minutes * 0.9 - 1 <= spent <= minutes * 1.1 + 1, (d, spent)
    # Неделя в целом — около бюджета.
    assert total == pytest.approx(minutes * 5, rel=0.15 if game + 10 <= minutes else 0.6)


def test_focus_and_allocation_follow_scores() -> None:
    plan = build_week_plan(WEAK, goal(), AVAIL, MONDAY, MONDAY)
    assert plan.focus == ("fork", "accuracy_endgame", "time_trouble_share")
    alloc = {a.kind: a for a in plan.allocation}
    assert "fork" in alloc["puzzles"].focus
    assert alloc["endgames"].focus == ("accuracy_endgame",)
    assert alloc["rush"].focus == ("time_trouble_share",)
    themed = sum(t.minutes for t in plan.tasks if t.params.get("theme") == "fork")
    endgame = alloc["endgames"].minutes_per_week
    rush = alloc["rush"].minutes_per_week
    # Пропорционально score: 80 > 60 > 40.
    assert themed > endgame > rush > 0
    assert sum(a.share for a in plan.allocation) == pytest.approx(1.0, abs=0.01)
    # Хрупкие ссылки: эндшпиль — свои позиции.
    assert all(t.params == {"tab": "mine"} for t in plan.tasks if t.kind == "endgames")
    assert all(t.params == {"bot_elo": 1700} for t in plan.tasks if t.kind == "play")


def test_lessons_one_per_focus_unread_first() -> None:
    avail = Availability(puzzles=200, read_lessons=frozenset({"fork"}))
    plan = build_week_plan(WEAK, goal(), avail, MONDAY, MONDAY)
    lessons = [t for t in plan.tasks if t.kind == "lesson"]
    assert [t.params["lesson"] for t in lessons] == [
        "endgame_technique",
        "time_management",
        "fork",
    ]
    assert [t.day for t in lessons] == list(plan.study_days[:3])
    assert all(t.target == 1 and t.minutes == 8 and t.unit == "lessons" for t in lessons)


def test_untrainable_weakness_gets_no_time() -> None:
    weak = [
        gap("fork", 80, theme="fork", available=0),
        gap("white:Sicilian", 70, kind="opening", train="course", eco="C00"),
        gap("conversion", 50, kind="metric", train=None, lesson="converting_advantage"),
    ]
    plan = build_week_plan(weak, goal(), AVAIL, MONDAY, MONDAY)
    kinds = {t.kind for t in plan.tasks}
    assert "course" not in kinds
    assert not any(t.params.get("theme") for t in plan.tasks)
    # Урок для слабости без тренировки всё равно ставится.
    assert [t.params["lesson"] for t in plan.tasks if t.kind == "lesson"] == [
        "converting_advantage"
    ]


def test_course_weakness_uses_user_course() -> None:
    weak = [gap("white:Sicilian", 70, kind="opening", train="course", eco="B90")]
    plan = build_week_plan(weak, goal(), AVAIL, MONDAY, MONDAY)
    course = [t for t in plan.tasks if t.kind == "course"]
    assert course
    assert all(t.params == {"course_id": "course-1"} and t.unit == "attempts" for t in course)


def test_no_weaknesses_and_no_puzzles() -> None:
    plan = build_week_plan([], goal(), Availability(puzzles=0), MONDAY, MONDAY)
    kinds = {t.kind for t in plan.tasks}
    # Пазлов нет — время тактики уходит в типовые эндшпили каталога и в партии.
    assert kinds <= {"play", "review", "endgames"}
    assert "play" in kinds
    assert all(t.params == {"tab": "catalog"} for t in plan.tasks if t.kind == "endgames")
    assert plan.focus == ()
    assert sum(t.target for t in plan.tasks if t.kind == "play") >= 3


def test_puzzle_minutes_capped_by_available_puzzles() -> None:
    plan = build_week_plan([], goal(minutes=60), Availability(puzzles=1), MONDAY, MONDAY)
    puzzles = sum(t.target for t in plan.tasks if t.kind == "puzzles")
    # Один пазл — не больше двух решений за неделю, остальное — каталог эндшпиля и партии.
    assert puzzles <= 2
    catalog = sum(t.target for t in plan.tasks if t.kind == "endgames")
    assert 0 < catalog <= 2 * 21


def test_high_target_lowers_tactics_floor() -> None:
    plan = build_week_plan([], goal(target=2400, minutes=60), AVAIL, MONDAY, MONDAY)
    by_kind = kind_minutes(plan.tasks)
    total = sum(by_kind.values())
    assert by_kind["puzzles"] / total >= 0.2 - 0.03


def test_rebuild_from_midweek_keeps_rules() -> None:
    thursday = MONDAY + timedelta(days=3)
    plan = build_week_plan(WEAK, goal(), AVAIL, MONDAY, thursday)
    assert {t.day for t in plan.tasks} == {MONDAY + timedelta(days=4), MONDAY + timedelta(days=5)}
    # Партия есть даже в короткой неделе, уроки — в оставшиеся дни.
    assert any(t.kind == "play" for t in plan.tasks)
    assert len([t for t in plan.tasks if t.kind == "lesson"]) == 3


def test_positions_and_units() -> None:
    plan = build_week_plan(WEAK, goal(), AVAIL, MONDAY, MONDAY)
    for d in plan.study_days:
        day = [t for t in plan.tasks if t.day == d]
        assert [t.position for t in day] == list(range(len(day)))
    review = [t for t in plan.tasks if t.kind == "review"]
    play = [t for t in plan.tasks if t.kind == "play"]
    assert sum(t.target for t in review) == sum(t.target for t in play)
    puzzles = next(t for t in plan.tasks if t.kind == "puzzles")
    assert (
        puzzles.minutes == round(puzzles.target * 1.5)
        or abs(puzzles.minutes - puzzles.target * 1.5) < 1
    )


def test_short_day_with_long_game() -> None:
    # 15 минут в день и рапид: партия длиннее дня — ставится одна, разбор — отдельным днём.
    plan = build_week_plan(WEAK, goal(minutes=15, days=3), AVAIL, MONDAY, MONDAY)
    play = [t for t in plan.tasks if t.kind == "play"]
    review = [t for t in plan.tasks if t.kind == "review"]
    assert sum(t.target for t in play) == 1
    assert sum(t.target for t in review) == 1
    assert review[0].day > play[0].day
