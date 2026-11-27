"""План недели и задания дня (17.2): ленивая сборка, автозачёт, серия, ссылки.

**Неделя и день** — по зоне цели (`goal.tz`): неделя с понедельника, границы дня — полночь
в этой зоне.

**Сборка** — при первом обращении в неделе (`/coach/today`, `/coach/plan`) по свежей
диагностике (`app.coach.diagnosis.diagnose`, 17.1) с сегодняшнего дня; `rebuild` — с сегодня,
не чаще раза в час (иначе текущий план): задания с сегодняшнего дня заменяются, прошедшие
остаются.

**Автозачёт** — прогресс за день по таблицам активности при каждом запросе:
- `puzzles` — `puzzle_attempts` (кроме забегов) с фильтром темы / фазы / дебюта задания;
- `rush` — `puzzle_rush_runs` (с темой, если задана); `endgames` — `endgame_attempts`
  (`tab=mine` — позиции своих партий, `catalog` — типовые); `course` — `trainer_attempts`
  по карточкам курса;
- `play` — партии дня: партии цели (площадка и контроль, `played_at` в этот день по зоне
  цели) и партии с ботом (см. `bot_game`);
- `lesson` — `coach_lesson_reads.read_at` в этот день; `review` — только вручную.
Норма выполнена — `done_at` (и прогресс) сохраняются; отметка вручную — тоже `done_at`.
Невыполненные задания прошедших дней пересчитываются, когда до них доходит серия или отчёт:
партию могли импортировать позже.

**Партии с ботом** попадают в БД, только когда пользователь нажимает «Разобрать партию»
(`bot-game.tsx` → `POST /games/pgn`): источник `pgn`, `Site "Chess Review"`, `Date` —
**локальная** дата браузера без `Time`, поэтому `played_at` = эта дата 00:00 UTC. Такую
партию засчитываем по её дате как есть (а не по зоне цели — иначе в западных зонах она уехала
бы на вчера); партия, импортированная позже, засчитывается в день игры. Партия с `Time` —
по зоне цели, как обычная.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, and_, case, cast, delete, func, or_, select
from sqlalchemy import Date as SaDate
from sqlalchemy import Time as SaTime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas_coach import (
    AllocationOut,
    DiagnosisOut,
    GapOut,
    GoalOut,
    PlanDayOut,
    PlanOut,
    TaskKind,
    TaskOut,
    TaskUnit,
    TodayOut,
)
from app.coach import diagnosis as diagnosis_module
from app.coach.planner import (
    UNITS,
    Availability,
    PlanGoal,
    allocation,
    build_week_plan,
    focus_of,
    week_start_of,
)
from app.db.models import (
    Analysis,
    CoachGoal,
    CoachLessonRead,
    CoachPlan,
    CoachTask,
    Course,
    CourseStatus,
    EndgameAttempt,
    Game,
    GameSource,
    Move,
    Puzzle,
    PuzzleAttempt,
    PuzzleRushRun,
    TrainerAttempt,
    TrainerCard,
    UserCourse,
)
from app.stats.queries import time_class_sql

REBUILD_INTERVAL = timedelta(hours=1)
BOT_SITE = '[Site "Chess Review"]'
BOT_MIN_ELO, BOT_MAX_ELO = 400, 2800
# Серия смотрит назад не дальше (учебных дней подряд больше — редкость, а запрос дешевле).
STREAK_MAX_DAYS = 400
# Ключ слабой стороны задания хранится в `params` (в модели нет своего столбца), наружу — `focus`.
FOCUS_KEY = "_focus"


# --- Время по зоне цели ----------------------------------------------------------------------


def now_utc() -> datetime:
    return datetime.now(UTC)


def local_today(goal: CoachGoal, now: datetime | None = None) -> date:
    return (now or now_utc()).astimezone(ZoneInfo(goal.tz)).date()


def day_bounds(day: date, tz: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(tz)
    start = datetime.combine(day, time(), zone)
    end = datetime.combine(day + timedelta(days=1), time(), zone)
    return start.astimezone(UTC), end.astimezone(UTC)


# --- Партии дня ------------------------------------------------------------------------------


def bot_game() -> ColumnElement[bool]:
    return and_(Game.source == GameSource.PGN, Game.pgn.contains(BOT_SITE))


def goal_game(goal: CoachGoal) -> ColumnElement[bool]:
    return and_(
        Game.source == goal.source,
        Game.user_color.is_not(None),
        time_class_sql(Game.__table__.c.time_control) == goal.time_class,
    )


def game_local_date(tz: str) -> ColumnElement[Any]:
    """Дата партии: у партии с ботом без времени — дата из PGN как есть, иначе — по зоне."""
    utc_date = cast(func.timezone("UTC", Game.played_at), SaDate)
    local = cast(func.timezone(tz, Game.played_at), SaDate)
    midnight = cast(func.timezone("UTC", Game.played_at), SaTime) == time()
    return case((and_(bot_game(), midnight), utc_date), else_=local)


def games_between(goal: CoachGoal, first: date, last: date) -> ColumnElement[bool]:
    """Партии цели и партии с ботом, сыгранные в дни [first, last] по зоне цели."""
    return and_(
        Game.user_id == goal.user_id,
        Game.played_at.is_not(None),
        or_(goal_game(goal), bot_game()),
        game_local_date(goal.tz).between(first, last),
    )


async def games_count(session: AsyncSession, goal: CoachGoal, first: date, last: date) -> int:
    stmt = select(func.count()).select_from(Game).where(games_between(goal, first, last))
    return int((await session.execute(stmt)).scalar_one())


async def latest_game_of_day(session: AsyncSession, goal: CoachGoal, day: date) -> uuid.UUID | None:
    return await session.scalar(
        select(Game.id)
        .where(games_between(goal, day, day))
        .order_by(Game.played_at.desc(), Game.created_at.desc())
        .limit(1)
    )


async def latest_goal_game(session: AsyncSession, goal: CoachGoal) -> uuid.UUID | None:
    return await session.scalar(
        select(Game.id)
        .where(Game.user_id == goal.user_id, goal_game(goal))
        .order_by(func.coalesce(Game.played_at, Game.created_at).desc())
        .limit(1)
    )


# --- Прогресс --------------------------------------------------------------------------------


def _puzzles_stmt(uid: uuid.UUID, p: dict[str, Any], start: datetime, end: datetime) -> Any:
    stmt = (
        select(func.count(PuzzleAttempt.id))
        .join(Puzzle, Puzzle.id == PuzzleAttempt.puzzle_id)
        .where(
            PuzzleAttempt.user_id == uid,
            PuzzleAttempt.mode != "rush",
            PuzzleAttempt.created_at >= start,
            PuzzleAttempt.created_at < end,
        )
    )
    if p.get("theme"):
        stmt = stmt.where(Puzzle.themes.contains([str(p["theme"])]))
    if p.get("phase") or p.get("eco"):
        stmt = stmt.join(Move, Move.id == Puzzle.move_id)
    if p.get("phase"):
        stmt = stmt.where(Move.phase == p["phase"])
    if p.get("eco"):
        stmt = (
            stmt.join(Analysis, Analysis.id == Move.analysis_id)
            .join(Game, Game.id == Analysis.game_id)
            .where(Game.opening_eco == p["eco"])
        )
    return stmt


def _rush_stmt(uid: uuid.UUID, p: dict[str, Any], start: datetime, end: datetime) -> Any:
    stmt = select(func.count(PuzzleRushRun.id)).where(
        PuzzleRushRun.user_id == uid,
        PuzzleRushRun.created_at >= start,
        PuzzleRushRun.created_at < end,
    )
    if p.get("theme"):
        stmt = stmt.where(PuzzleRushRun.filters["theme"].astext == str(p["theme"]))
    return stmt


def _endgames_stmt(uid: uuid.UUID, p: dict[str, Any], start: datetime, end: datetime) -> Any:
    stmt = select(func.count(EndgameAttempt.id)).where(
        EndgameAttempt.user_id == uid,
        EndgameAttempt.created_at >= start,
        EndgameAttempt.created_at < end,
    )
    tab = p.get("tab")
    if tab in {"mine", "catalog"}:
        stmt = stmt.where(EndgameAttempt.source == ("game" if tab == "mine" else "catalog"))
    return stmt


def _course_stmt(uid: uuid.UUID, p: dict[str, Any], start: datetime, end: datetime) -> Any:
    stmt = (
        select(func.count(TrainerAttempt.id))
        .join(TrainerCard, TrainerCard.id == TrainerAttempt.card_id)
        .where(
            TrainerAttempt.user_id == uid,
            TrainerAttempt.created_at >= start,
            TrainerAttempt.created_at < end,
        )
    )
    if p.get("course_id"):
        stmt = stmt.where(TrainerCard.course_id == uuid.UUID(str(p["course_id"])))
    return stmt


def _lesson_stmt(uid: uuid.UUID, p: dict[str, Any], start: datetime, end: datetime) -> Any:
    return select(func.count()).where(
        CoachLessonRead.user_id == uid,
        CoachLessonRead.key == str(p.get("lesson")),
        CoachLessonRead.read_at >= start,
        CoachLessonRead.read_at < end,
    )


_PROGRESS = {
    "puzzles": _puzzles_stmt,
    "rush": _rush_stmt,
    "endgames": _endgames_stmt,
    "course": _course_stmt,
    "lesson": _lesson_stmt,
}


async def task_progress(session: AsyncSession, goal: CoachGoal, task: CoachTask) -> int:
    """Прогресс задания за его день по таблицам активности (см. модуль)."""
    if task.kind == "play":
        return await games_count(session, goal, task.day, task.day)
    build = _PROGRESS.get(task.kind)
    if build is None:
        return task.progress
    start, end = day_bounds(task.day, goal.tz)
    stmt = build(goal.user_id, task.params or {}, start, end)
    return int((await session.execute(stmt)).scalar_one())


async def refresh_task(
    session: AsyncSession, goal: CoachGoal, task: CoachTask, now: datetime
) -> None:
    """Пересчитать прогресс; норма выполнена — `done_at` (без коммита)."""
    if task.kind == "review":
        return
    progress = await task_progress(session, goal, task)
    if progress != task.progress:
        task.progress = progress
    if task.done_at is None and progress >= task.target:
        task.done_at = now


# --- Ссылки ----------------------------------------------------------------------------------


def _query(base: dict[str, str], params: dict[str, Any], keys: tuple[str, ...]) -> str:
    return urlencode(base | {k: str(params[k]) for k in keys if params.get(k)})


def task_href(kind: str, params: dict[str, Any]) -> str:
    """Ссылка задания (страницы сессии 16, курсы, игра, разбор, урок)."""
    tab = params.get("tab") if params.get("tab") in {"mine", "catalog"} else "mine"
    game = params.get("game_id")
    hrefs = {
        "puzzles": f"/puzzles?{_query({'mode': 'practice'}, params, ('theme', 'phase', 'eco'))}",
        "rush": f"/puzzles?{_query({'mode': 'rush'}, params, ('theme',))}",
        "endgames": f"/play/endgames?tab={tab}",
        "course": f"/openings/train?{urlencode({'course': str(params.get('course_id', ''))})}",
        "play": "/play",
        "review": f"/games/{game}" if game else "/games",
        "lesson": f"/coach/lessons/{params.get('lesson', '')}",
    }
    return hrefs.get(kind, "/coach")


def task_out(task: CoachTask, extra: dict[str, Any] | None = None) -> TaskOut:
    params: dict[str, str | int] = {
        k: v for k, v in {**(task.params or {}), **(extra or {})}.items() if k != FOCUS_KEY
    }
    kind: TaskKind = task.kind  # type: ignore[assignment]
    unit: TaskUnit = UNITS[kind]
    return TaskOut(
        id=task.id,
        day=task.day,
        position=task.position,
        kind=kind,
        params=params,
        target=task.target,
        progress=task.progress,
        unit=unit,
        minutes=task.minutes,
        done=task.done_at is not None,
        done_at=task.done_at,
        href=task_href(kind, params),
        focus=_focus(task),
    )


def _focus(task: CoachTask) -> str | None:
    value = (task.params or {}).get(FOCUS_KEY)
    return None if value is None else str(value)


# --- Сборка плана ----------------------------------------------------------------------------


def bot_elo_for(rating: int) -> int:
    return min(BOT_MAX_ELO, max(BOT_MIN_ELO, round(rating / 100) * 100))


async def availability(session: AsyncSession, user_id: uuid.UUID, rating: int) -> Availability:
    puzzles = int(
        (
            await session.execute(select(func.count(Puzzle.id)).where(Puzzle.user_id == user_id))
        ).scalar_one()
    )
    courses = await session.execute(
        select(Course.eco, Course.id)
        .join(UserCourse, UserCourse.course_id == Course.id)
        .where(
            UserCourse.user_id == user_id,
            Course.status == CourseStatus.READY,
            Course.eco.is_not(None),
        )
        .order_by(UserCourse.added_at)
    )
    by_eco = {eco: str(course_id) for eco, course_id in courses if eco}
    reads = await session.scalars(
        select(CoachLessonRead.key).where(CoachLessonRead.user_id == user_id)
    )
    return Availability(
        puzzles=puzzles,
        courses_by_eco=by_eco,
        read_lessons=frozenset(reads),
        bot_elo=bot_elo_for(rating),
    )


async def run_diagnosis(session: AsyncSession, goal: CoachGoal) -> DiagnosisOut:
    return await diagnosis_module.diagnose(session, goal.user_id, goal)


def _plan_goal(goal: CoachGoal) -> PlanGoal:
    return PlanGoal(
        time_class=goal.time_class,  # type: ignore[arg-type]
        target_rating=goal.target_rating,
        minutes_per_day=goal.minutes_per_day,
        days_per_week=goal.days_per_week,
    )


async def _fill(
    session: AsyncSession,
    goal: CoachGoal,
    plan: CoachPlan,
    diag: DiagnosisOut,
    from_day: date,
) -> None:
    avail = await availability(session, goal.user_id, diag.current_rating)
    week = build_week_plan(diag.weaknesses, _plan_goal(goal), avail, plan.week_start, from_day)
    plan.diagnosis = diag.model_dump(mode="json")
    plan.allocation = [
        {
            "kind": a.kind,
            "minutes_per_week": a.minutes_per_week,
            "share": a.share,
            "focus": list(a.focus),
        }
        for a in week.allocation
    ]
    for spec in week.tasks:
        params: dict[str, Any] = dict(spec.params)
        if spec.focus:
            params[FOCUS_KEY] = spec.focus
        session.add(
            CoachTask(
                plan_id=plan.id,
                user_id=goal.user_id,
                day=spec.day,
                position=spec.position,
                kind=spec.kind,
                params=params,
                target=spec.target,
                progress=0,
                minutes=spec.minutes,
            )
        )


async def week_plan(session: AsyncSession, goal: CoachGoal, week_start: date) -> CoachPlan | None:
    return await session.scalar(
        select(CoachPlan).where(CoachPlan.goal_id == goal.id, CoachPlan.week_start == week_start)
    )


async def ensure_plan(session: AsyncSession, goal: CoachGoal, today: date) -> CoachPlan:
    """План текущей недели; нет — собрать с сегодня (коммит — здесь)."""
    start = week_start_of(today)
    plan = await week_plan(session, goal, start)
    if plan is not None:
        return plan
    diag = await run_diagnosis(session, goal)
    plan = CoachPlan(
        goal_id=goal.id, week_start=start, diagnosis={}, allocation=[], created_at=now_utc()
    )
    try:
        # Точка сохранения: при гонке откатывается только вставка плана, а не вся сессия —
        # иначе `goal` и другие объекты истекают, и обращение к ним из async-кода падает
        # с MissingGreenlet (так было при одновременных /coach/today и /coach/plan).
        async with session.begin_nested():
            session.add(plan)
            await session.flush()
    except IntegrityError:
        # Параллельный запрос уже собрал план этой недели.
        existing = await week_plan(session, goal, start)
        assert existing is not None
        return existing
    await _fill(session, goal, plan, diag, today)
    await session.commit()
    await session.refresh(plan)
    return plan


async def rebuild_plan(
    session: AsyncSession, goal: CoachGoal, today: date, now: datetime
) -> CoachPlan:
    """Пересобрать с сегодня; план моложе часа — вернуть как есть."""
    plan = await week_plan(session, goal, week_start_of(today))
    if plan is None:
        return await ensure_plan(session, goal, today)
    if now - plan.created_at < REBUILD_INTERVAL:
        return plan
    diag = await run_diagnosis(session, goal)
    await session.execute(
        delete(CoachTask).where(CoachTask.plan_id == plan.id, CoachTask.day >= today)
    )
    plan.created_at = now
    plan.forecast = None
    await _fill(session, goal, plan, diag, today)
    await session.commit()
    await session.refresh(plan)
    return plan


async def plan_tasks(session: AsyncSession, plan: CoachPlan) -> list[CoachTask]:
    rows = await session.scalars(
        select(CoachTask)
        .where(CoachTask.plan_id == plan.id)
        .order_by(CoachTask.day, CoachTask.position, CoachTask.id)
    )
    return list(rows)


async def refresh_tasks(
    session: AsyncSession, goal: CoachGoal, tasks: Sequence[CoachTask], today: date
) -> None:
    """Пересчитать задания по сегодня включительно: сегодняшние — всегда, прошлые —
    только невыполненные (коммит — здесь)."""
    now = now_utc()
    for task in tasks:
        if task.day > today or (task.day < today and task.done_at is not None):
            continue
        await refresh_task(session, goal, task, now)
    await session.commit()


async def _review_extra(
    session: AsyncSession, goal: CoachGoal, task: CoachTask
) -> dict[str, Any] | None:
    """Разбор ведёт к последней партии дня, иначе — к последней партии цели."""
    if task.kind != "review" or (task.params or {}).get("game_id"):
        return None
    game = await latest_game_of_day(session, goal, task.day) or await latest_goal_game(
        session, goal
    )
    return None if game is None else {"game_id": str(game)}


async def tasks_out(
    session: AsyncSession, goal: CoachGoal, tasks: Sequence[CoachTask]
) -> list[TaskOut]:
    out = []
    for task in tasks:
        out.append(task_out(task, await _review_extra(session, goal, task)))
    return out


# --- Серия -----------------------------------------------------------------------------------


async def streak_days(session: AsyncSession, goal: CoachGoal, today: date) -> int:
    """Учебные дни подряд со всеми заданиями: от вчера назад (выходные пропускаются, неделя без
    плана рвёт серию) плюс сегодня, если всё выполнено."""
    weeks = set(
        await session.scalars(select(CoachPlan.week_start).where(CoachPlan.goal_id == goal.id))
    )
    if not weeks:
        return 0
    first = min(weeks)
    rows = list(
        await session.scalars(
            select(CoachTask)
            .join(CoachPlan, CoachPlan.id == CoachTask.plan_id)
            .where(
                CoachPlan.goal_id == goal.id,
                CoachTask.day <= today,
                CoachTask.day >= today - timedelta(days=STREAK_MAX_DAYS),
            )
        )
    )
    by_day: dict[date, list[CoachTask]] = {}
    for task in rows:
        by_day.setdefault(task.day, []).append(task)
    now = now_utc()

    async def all_done(day: date) -> bool:
        tasks = by_day[day]
        for task in tasks:
            if task.done_at is None:
                await refresh_task(session, goal, task, now)
        return all(t.done_at is not None for t in tasks)

    streak = 0
    day = today - timedelta(days=1)
    while day >= first and (today - day).days <= STREAK_MAX_DAYS:
        if week_start_of(day) not in weeks:
            break
        if day in by_day:
            if not await all_done(day):
                break
            streak += 1
        day -= timedelta(days=1)
    if today in by_day and await all_done(today):
        streak += 1
    await session.commit()
    return streak


# --- Ответы ----------------------------------------------------------------------------------


def _minutes_done(tasks: Sequence[TaskOut]) -> int:
    total = 0.0
    for t in tasks:
        share = 1.0 if t.done else min(1.0, t.progress / t.target) if t.target else 0.0
        total += t.minutes * share
    return round(total)


async def today_out(session: AsyncSession, goal: CoachGoal, goal_view: GoalOut) -> TodayOut:
    today = local_today(goal)
    plan = await ensure_plan(session, goal, today)
    todays = [t for t in await plan_tasks(session, plan) if t.day == today]
    await refresh_tasks(session, goal, todays, today)
    streak = await streak_days(session, goal, today)
    items = await tasks_out(session, goal, todays)
    return TodayOut(
        goal=goal_view,
        day=today,
        rest_day=not items,
        tasks=items,
        minutes_total=sum(t.minutes for t in items),
        minutes_done=_minutes_done(items),
        streak_days=streak,
    )


def plan_focus(plan: CoachPlan) -> list[GapOut]:
    raw = (plan.diagnosis or {}).get("weaknesses") or []
    return focus_of([GapOut.model_validate(g) for g in raw])


async def plan_out(
    session: AsyncSession, goal: CoachGoal, goal_view: GoalOut, plan: CoachPlan
) -> PlanOut:
    today = local_today(goal)
    tasks = await plan_tasks(session, plan)
    await refresh_tasks(session, goal, tasks, today)
    items = await tasks_out(session, goal, tasks)
    days = []
    for i in range(7):
        day = plan.week_start + timedelta(days=i)
        day_tasks = [t for t in items if t.day == day]
        days.append(
            PlanDayOut(
                day=day,
                rest_day=not day_tasks,
                minutes=sum(t.minutes for t in day_tasks),
                tasks=day_tasks,
            )
        )
    return PlanOut(
        goal=goal_view,
        week_start=plan.week_start,
        created_at=plan.created_at,
        focus=plan_focus(plan),
        allocation=[
            AllocationOut(
                kind=a.kind, minutes_per_week=a.minutes_per_week, share=a.share, focus=list(a.focus)
            )
            for a in allocation(items)
        ],
        days=days,
        next_rebuild=plan.week_start + timedelta(days=7),
    )


async def mark_done(
    session: AsyncSession, user_id: uuid.UUID, task_id: int
) -> tuple[CoachTask, CoachGoal] | None:
    """Отметить задание вручную; чужое или нет — `None`."""
    row = (
        await session.execute(
            select(CoachTask, CoachGoal)
            .join(CoachPlan, CoachPlan.id == CoachTask.plan_id)
            .join(CoachGoal, CoachGoal.id == CoachPlan.goal_id)
            .where(CoachTask.id == task_id, CoachTask.user_id == user_id)
        )
    ).first()
    if row is None:
        return None
    task, goal = row
    if task.done_at is None:
        task.done_at = now_utc()
        task.progress = max(task.progress, task.target)
        await session.commit()
        await session.refresh(task)
    return task, goal


async def mark_lesson_tasks(
    session: AsyncSession, goal: CoachGoal, key: str, now: datetime
) -> None:
    """Прочитан урок — засчитать задания с ним на сегодня (без коммита)."""
    today = local_today(goal, now)
    tasks = await session.scalars(
        select(CoachTask)
        .join(CoachPlan, CoachPlan.id == CoachTask.plan_id)
        .where(
            CoachPlan.goal_id == goal.id,
            CoachTask.kind == "lesson",
            CoachTask.day == today,
            CoachTask.params["lesson"].astext == key,
            CoachTask.done_at.is_(None),
        )
    )
    for task in tasks:
        task.progress = task.target
        task.done_at = now
