"""Слабые места (сессия 16.1): выводы по разобранным партиям с примерами и тренировкой."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StatsFilters
from app.api.schemas_insights import InsightsOut, insights_out
from app.db.models import GameSource
from app.insights.queries import user_insights
from app.review.game_rating import TimeClass

router = APIRouter(tags=["insights"])


@router.get("/insights/me")
async def my_insights(
    session: SessionDep,
    user: CurrentUser,
    source: GameSource | None = None,
    time_class: TimeClass | None = None,
) -> InsightsOut:
    """Слабые места по партиям пользователя: пропущенные мотивы, фазы, время, дебюты,
    реализация выигранных позиций — по важности, с примерами и ссылкой на тренировку.
    Пока разобранных партий меньше `min_games`, `findings` пуст. Фильтры — как у `/stats/me`."""
    result = await user_insights(session, user.id, source=source, time_class=time_class)
    return insights_out(result, StatsFilters(source=source, time_class=time_class))
