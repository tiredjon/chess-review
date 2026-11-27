"""Тренер — диагностика (сессия 17.1): метрики пользователя против эталонов его группы и
целевой, сильные и слабые стороны. Контракт — SPEC «Сессия 17» и `schemas_coach.py`."""

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ApiError
from app.api.schemas_coach import DiagnosisOut
from app.coach.diagnosis import diagnose
from app.core.errors import ErrorCode
from app.db.models import CoachGoal

router = APIRouter(tags=["coach"])


@router.get("/coach/diagnosis")
async def coach_diagnosis(session: SessionDep, user: CurrentUser) -> DiagnosisOut:
    """Диагностика по партиям активной цели (площадка + контроль). Нет цели — 404
    `coach_goal_not_found`; разобранных партий меньше `min_games` — метрики
    `insufficient`, сильные и слабые стороны пусты."""
    goal = await session.scalar(
        select(CoachGoal).where(CoachGoal.user_id == user.id, CoachGoal.archived_at.is_(None))
    )
    if goal is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.COACH_GOAL_NOT_FOUND, "Цели нет")
    return await diagnose(session, user.id, goal)
