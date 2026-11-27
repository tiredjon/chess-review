"""Тренер — цель, план, задания дня, прогноз, уроки (сессия 17.2).

Контракт — SPEC «Сессия 17» и `schemas_coach.py`; логика — `app/coach/{goal,planner,tasks,
forecast,report,lessons_api}.py`. Диагностику (17.1) план берёт из
`app.coach.diagnosis.diagnose`.
"""

from fastapi import APIRouter, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ApiError, ErrorCode
from app.api.schemas_coach import (
    ForecastOut,
    GoalIn,
    GoalOut,
    GoalStateOut,
    LessonItemOut,
    LessonListOut,
    LessonOut,
    PlanOut,
    ReportOut,
    TaskOut,
    TodayOut,
)
from app.coach import goal as goals
from app.coach import lessons_api, report, tasks
from app.coach.lessons import LESSONS
from app.coach.planner import week_start_of
from app.db.models import CoachGoal, User

router = APIRouter(tags=["coach"])


def _validation(message: str, field: str) -> ApiError:
    return ApiError(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        message,
        params={"field": field},
    )


async def _goal(session: AsyncSession, user: User) -> tuple[CoachGoal, GoalOut]:
    goal = await goals.active_goal(session, user.id)
    if goal is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COACH_GOAL_NOT_FOUND, "no active goal")
    return goal, await goals.refresh_goal(session, goal)


# --- Цель ------------------------------------------------------------------------------------


@router.get("/coach/goal")
async def get_goal(session: SessionDep, user: CurrentUser) -> GoalStateOut:
    """Активная цель (или `null`) и рейтинги по последней партии в каждой паре площадка ×
    контроль — варианты для мастера цели."""
    goal = await goals.active_goal(session, user.id)
    view = None if goal is None else await goals.refresh_goal(session, goal)
    return GoalStateOut(goal=view, ratings=await goals.ratings(session, user.id))


@router.put("/coach/goal")
async def put_goal(body: GoalIn, session: SessionDep, user: CurrentUser) -> GoalOut:
    """Новая цель (прежняя архивируется). `start_rating` — текущий рейтинг; цель должна быть
    выше него (иначе 422 `validation_error`); нет партий — 422 `coach_no_rating`."""
    if not goals.valid_tz(body.tz):
        raise _validation(f"unknown time zone {body.tz!r}", "tz")
    current = await goals.current_rating(session, user.id, body.source, body.time_class)
    if current is None:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.COACH_NO_RATING,
            "no rated games for this source and time class",
            params={"source": body.source, "time_class": body.time_class},
        )
    if body.target_rating <= current:
        raise _validation("target_rating must be above the current rating", "target_rating")
    goal = await goals.set_goal(session, user.id, body, current)
    return goals.goal_out(goal, current)


@router.delete("/coach/goal", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(session: SessionDep, user: CurrentUser) -> Response:
    """Архивировать активную цель (её планы и задания остаются в истории)."""
    await goals.archive_goal(session, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- План и задания --------------------------------------------------------------------------


@router.get("/coach/today")
async def get_today(session: SessionDep, user: CurrentUser) -> TodayOut:
    """Задания на сегодня по зоне цели; прогресс — по таблицам активности при каждом запросе.
    Плана на эту неделю нет — собирается сейчас."""
    goal, view = await _goal(session, user)
    return await tasks.today_out(session, goal, view)


@router.get("/coach/plan")
async def get_plan(session: SessionDep, user: CurrentUser) -> PlanOut:
    """План текущей недели (собирается при первом обращении в неделе)."""
    goal, view = await _goal(session, user)
    plan = await tasks.ensure_plan(session, goal, tasks.local_today(goal))
    return await tasks.plan_out(session, goal, view, plan)


@router.post("/coach/plan/rebuild")
async def rebuild_plan(session: SessionDep, user: CurrentUser) -> PlanOut:
    """Пересобрать план с сегодня по свежей диагностике; не чаще раза в час — иначе текущий."""
    goal, view = await _goal(session, user)
    plan = await tasks.rebuild_plan(session, goal, tasks.local_today(goal), tasks.now_utc())
    return await tasks.plan_out(session, goal, view, plan)


@router.post("/coach/tasks/{task_id}/done")
async def task_done(task_id: int, session: SessionDep, user: CurrentUser) -> TaskOut:
    """Отметить задание выполненным вручную (разбор, урок или любое другое)."""
    found = await tasks.mark_done(session, user.id, task_id)
    if found is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COACH_TASK_NOT_FOUND, "task not found")
    task, goal = found
    return (await tasks.tasks_out(session, goal, [task]))[0]


@router.get("/coach/report")
async def get_report(session: SessionDep, user: CurrentUser) -> ReportOut:
    """Отчёт за прошлую неделю плана (`null` — её не было)."""
    goal, _ = await _goal(session, user)
    return ReportOut(report=await report.week_report(session, goal))


@router.get("/coach/forecast")
async def get_forecast(session: SessionDep, user: CurrentUser) -> ForecastOut:
    """Срок цели диапазоном (p50 / p80), вероятность за год и коридор рейтинга по неделям.
    Это оценка, не обещание; при эталоне-заглушке — `confidence: low`."""
    goal, view = await _goal(session, user)
    fc = await report.user_forecast(session, goal, view)
    plan = await tasks.week_plan(session, goal, week_start_of(tasks.local_today(goal)))
    if plan is not None:
        await report.remember_forecast(session, plan, fc)
    return fc


# --- Уроки -----------------------------------------------------------------------------------


@router.get("/coach/lessons")
async def list_lessons(session: SessionDep, user: CurrentUser) -> LessonListOut:
    return LessonListOut(lessons=await lessons_api.lesson_list(session, user.id))


def _lesson_key(key: str) -> str:
    if key not in LESSONS:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.LESSON_NOT_FOUND, "unknown lesson")
    return key


@router.get("/coach/lessons/{key}")
async def get_lesson(key: str, session: SessionDep, user: CurrentUser) -> LessonOut:
    """Позиции из своих партий к уроку и ссылка на тренировку (текст — на фронте)."""
    _lesson_key(key)
    goal = await goals.active_goal(session, user.id)
    kind, read, examples, train = await lessons_api.lesson_detail(session, user.id, key, goal)
    return LessonOut(key=key, kind=kind, read=read, examples=examples, train=train)


@router.post("/coach/lessons/{key}/read")
async def read_lesson(key: str, session: SessionDep, user: CurrentUser) -> LessonItemOut:
    """Урок прочитан; засчитывает сегодняшнее задание с этим уроком."""
    _lesson_key(key)
    now = tasks.now_utc()
    await lessons_api.mark_read(session, user.id, key, now)
    goal = await goals.active_goal(session, user.id)
    if goal is not None:
        await tasks.mark_lesson_tasks(session, goal, key, now)
    await session.commit()
    return LessonItemOut(key=key, kind=LESSONS[key], read=True)
