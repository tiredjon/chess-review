"""Статистика пользователя по партиям."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StatsOut
from app.db.models import GameSource
from app.review.game_rating import TimeClass
from app.stats.queries import user_stats

router = APIRouter(tags=["stats"])


@router.get("/stats/me")
async def my_stats(
    session: SessionDep,
    user: CurrentUser,
    source: GameSource | None = None,
    time_class: TimeClass | None = None,
) -> StatsOut:
    """Агрегаты по партиям пользователя: точность во времени, дебюты, фазы, классы ходов,
    частые мотивы ошибок. Фильтры — по источнику и контролю времени."""
    return await user_stats(session, user.id, source=source, time_class=time_class)
