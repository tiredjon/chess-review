"""Репертуар пользователя: дебюты и дерево ходов из его партий (сессия 13)."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.db.models import Color
from app.repertoire.service import repertoire_openings, repertoire_tree
from app.repertoire.types import RepertoireOpening, RepertoireTree

router = APIRouter(tags=["repertoire"])

MAX_PLY_LIMIT = 40


@router.get("/repertoire/openings")
async def openings(session: SessionDep, user: CurrentUser, color: Color) -> list[RepertoireOpening]:
    """Дебюты пользователя за цвет: результат, частая линия, выход из книги. По убыванию партий."""
    return await repertoire_openings(session, user.id, color)


@router.get("/repertoire/tree")
async def tree(
    session: SessionDep,
    user: CurrentUser,
    color: Color,
    max_ply: Annotated[int, Query(ge=1, le=MAX_PLY_LIMIT)] = 24,
    min_games: Annotated[int, Query(ge=1, le=1000)] = 2,
) -> RepertoireTree:
    """Дерево ходов из партий за цвет до `max_ply` полуходов; узлы реже `min_games` отрезаны."""
    return await repertoire_tree(session, user.id, color, max_ply=max_ply, min_games=min_games)
