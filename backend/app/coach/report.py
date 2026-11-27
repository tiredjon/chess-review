"""Отчёт за неделю и данные прогноза (17.2) — сборка из БД; модель прогноза — `forecast.py`.

История рейтинга — партии цели (площадка + контроль) с рейтингом пользователя: по неделям
(с понедельника по зоне цели) — рейтинг последней партии недели и число партий, за 52 недели.
`adherence` — доля выполненных заданий за последние 4 недели плана (сегодняшние невыполненные
не считаются — день не кончился). Опорная p50-линия для `status` — первый прогноз плана этой
цели с датой p50.
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas_coach import (
    DiagnosisOut,
    ForecastOut,
    GoalOut,
    MetricDeltaOut,
    MetricOut,
    WeekReportOut,
)
from app.coach import tasks as coach_tasks
from app.coach.forecast import ForecastInput, RatingWeek, Reference, forecast
from app.coach.norms_data import load_trajectories
from app.coach.planner import week_start_of
from app.coach.tasks import (
    day_bounds,
    games_count,
    goal_game,
    local_today,
    plan_tasks,
    refresh_task,
    run_diagnosis,
)
from app.db.models import CoachGoal, CoachPlan, CoachTask, Color, Game

HISTORY_WEEKS = 52
TREND_WEEKS = 12
ADHERENCE_WEEKS = 4


async def rated_games(session: AsyncSession, goal: CoachGoal) -> list[tuple[datetime, int]]:
    """(время, рейтинг пользователя) партий цели по времени."""
    rating = case((Game.user_color == Color.WHITE, Game.white_elo), else_=Game.black_elo)
    rows = await session.execute(
        select(Game.played_at, rating)
        .where(
            Game.user_id == goal.user_id,
            goal_game(goal),
            Game.played_at.is_not(None),
            rating.is_not(None),
        )
        .order_by(Game.played_at, Game.id)
    )
    return [(played_at, int(value)) for played_at, value in rows]


def weekly_history(
    games: Sequence[tuple[datetime, int]], tz: str, today: date, weeks: int = HISTORY_WEEKS
) -> list[RatingWeek]:
    zone = ZoneInfo(tz)
    since = week_start_of(today) - timedelta(weeks=weeks)
    by_week: dict[date, tuple[int, int]] = {}
    for played_at, rating in games:
        week = week_start_of(played_at.astimezone(zone).date())
        if week < since:
            continue
        _, count = by_week.get(week, (rating, 0))
        by_week[week] = (rating, count + 1)
    return [RatingWeek(week, rating, count) for week, (rating, count) in sorted(by_week.items())]


def games_per_week(games: Sequence[tuple[datetime, int]], now: datetime) -> float:
    since = now - timedelta(weeks=TREND_WEEKS)
    recent = [g for g, _ in games if g >= since]
    if not recent:
        return 0.0
    span = max(1.0, min(TREND_WEEKS, (now - recent[0]).days / 7))
    return len(recent) / span


async def adherence(session: AsyncSession, goal: CoachGoal, today: date) -> float | None:
    since = week_start_of(today) - timedelta(weeks=ADHERENCE_WEEKS - 1)
    items = list(
        await session.scalars(
            select(CoachTask)
            .join(CoachPlan, CoachPlan.id == CoachTask.plan_id)
            .where(
                CoachPlan.goal_id == goal.id,
                CoachTask.day >= since,
                CoachTask.day <= today,
            )
        )
    )
    counted = [t for t in items if t.day < today or t.done_at is not None]
    if not counted:
        return None
    return round(sum(t.done_at is not None for t in counted) / len(counted), 3)


async def _reference(session: AsyncSession, goal: CoachGoal) -> Reference | None:
    plans = await session.scalars(
        select(CoachPlan)
        .where(CoachPlan.goal_id == goal.id, CoachPlan.forecast.is_not(None))
        .order_by(CoachPlan.week_start, CoachPlan.id)
    )
    for plan in plans:
        fc = plan.forecast or {}
        if fc.get("date_p50") and fc.get("current_rating") is not None:
            day = plan.created_at.astimezone(ZoneInfo(goal.tz)).date()
            return Reference(day, int(fc["current_rating"]), date.fromisoformat(fc["date_p50"]))
    return None


async def user_forecast(session: AsyncSession, goal: CoachGoal, view: GoalOut) -> ForecastOut:
    now = coach_tasks.now_utc()
    today = local_today(goal, now)
    games = await rated_games(session, goal)
    plan_weeks = int(
        (
            await session.execute(
                select(func.count(CoachPlan.id)).where(CoachPlan.goal_id == goal.id)
            )
        ).scalar_one()
    )
    inp = ForecastInput(
        today=today,
        time_class=goal.time_class,
        start_rating=goal.start_rating,
        current_rating=view.current_rating,
        target_rating=goal.target_rating,
        history=weekly_history(games, goal.tz, today),
        user_games=len(games),
        games_per_week=games_per_week(games, now),
        adherence=await adherence(session, goal, today),
        plan_weeks=plan_weeks,
        reference=await _reference(session, goal),
    )
    return forecast(inp, load_trajectories())


async def remember_forecast(session: AsyncSession, plan: CoachPlan, fc: ForecastOut) -> None:
    """Первый прогноз недели сохраняется в плане — от него меряется `status`."""
    if plan.forecast is None:
        plan.forecast = fc.model_dump(mode="json")
        await session.commit()


# --- Отчёт -----------------------------------------------------------------------------------


def _metric_values(diag: DiagnosisOut | None) -> dict[tuple[str, str], MetricOut]:
    return {} if diag is None else {(m.kind, m.key): m for m in diag.metrics}


def metric_deltas(before: DiagnosisOut | None, after: DiagnosisOut | None) -> list[MetricDeltaOut]:
    old, new = _metric_values(before), _metric_values(after)
    keys = list(old) + [k for k in new if k not in old]
    return [
        MetricDeltaOut(
            kind=(old.get(k) or new[k]).kind,
            key=k[1],
            before=old[k].value if k in old else None,
            after=new[k].value if k in new else None,
            direction=(old.get(k) or new[k]).direction,
        )
        for k in keys
    ]


def rating_at(games: Sequence[tuple[datetime, int]], moment: datetime) -> int | None:
    """Рейтинг по последней партии до `moment`."""
    value = None
    for played_at, rating in games:
        if played_at >= moment:
            break
        value = rating
    return value


async def week_report(session: AsyncSession, goal: CoachGoal) -> WeekReportOut | None:
    today = local_today(goal)
    plan = await session.scalar(
        select(CoachPlan)
        .where(CoachPlan.goal_id == goal.id, CoachPlan.week_start < week_start_of(today))
        .order_by(CoachPlan.week_start.desc())
        .limit(1)
    )
    if plan is None:
        return None
    tasks = await plan_tasks(session, plan)
    now = coach_tasks.now_utc()
    for task in tasks:
        if task.done_at is None:
            await refresh_task(session, goal, task, now)
    await session.commit()
    last_day = plan.week_start + timedelta(days=6)
    start, _ = day_bounds(plan.week_start, goal.tz)
    _, end = day_bounds(last_day, goal.tz)
    games = await rated_games(session, goal)
    in_week = [r for t, r in games if start <= t < end]
    before = None
    if plan.diagnosis:
        before = DiagnosisOut.model_validate(plan.diagnosis)
    after = await run_diagnosis(session, goal)
    done = [t for t in tasks if t.done_at is not None]
    return WeekReportOut(
        week_start=plan.week_start,
        tasks_total=len(tasks),
        tasks_done=len(done),
        minutes_done=sum(t.minutes for t in done),
        games_played=await games_count(session, goal, plan.week_start, last_day),
        rating_start=rating_at(games, start) or (in_week[0] if in_week else None),
        rating_end=rating_at(games, end),
        metrics=metric_deltas(before, after),
    )
