"""Сохранение импортированных партий: идемпотентно по unique(source, external_id, user_id)."""

import dataclasses
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Color, Game, GameSource, User
from app.importers.types import ImportedGame


def user_color(game: ImportedGame, usernames: Iterable[str | None]) -> Color | None:
    """Цвет пользователя по его никам (без учёта регистра); None — не его партия
    или он играл сам с собой."""
    names = {name.casefold() for name in usernames if name}
    white, black = game.white.casefold() in names, game.black.casefold() in names
    if white == black:
        return None
    return Color.WHITE if white else Color.BLACK


async def save_games(
    session: AsyncSession, user: User, source: GameSource, games: Sequence[ImportedGame]
) -> list[Game]:
    """Сохраняет партии и возвращает их строки — новые и уже бывшие — в порядке входа,
    без повторов. Коммит — за вызывающим."""
    unique = list({game.external_id: game for game in games}.values())
    if not unique:
        return []
    usernames = (user.lichess_username, user.chesscom_username)
    rows = [
        {
            **{field.name: getattr(game, field.name) for field in dataclasses.fields(game)},
            "user_color": game.user_color or user_color(game, usernames),
            "user_id": user.id,
            "source": source,
        }
        for game in unique
    ]
    await session.execute(insert(Game).values(rows).on_conflict_do_nothing())
    ids = [game.external_id for game in unique]
    found = await session.scalars(
        select(Game).where(
            Game.user_id == user.id, Game.source == source, Game.external_id.in_(ids)
        )
    )
    by_id = {game.external_id: game for game in found}
    return [by_id[external_id] for external_id in ids]
