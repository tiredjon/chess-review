"""Загрузка партий пользователя для репертуара: разбор PGN и кэш в памяти процесса.

Разбор PGN — самая дорогая часть (сотни партий), поэтому разобранные партии лежат в кэше по
ключу (пользователь, цвет, число партий, max(created_at)): добавление и удаление партий меняет
ключ. Новых таблиц нет; кэш ограничен по размеру и выбрасывает старейшие записи.
"""

import asyncio
import io
import uuid
from collections import OrderedDict
from collections.abc import Sequence
from datetime import datetime

import chess
import chess.pgn
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Color, Game
from app.repertoire.tree import (
    STORED_PLIES,
    RepertoireGame,
    build_tree,
    game_line,
    opening_list,
)
from app.repertoire.types import RepertoireOpening, RepertoireTree

CACHE_SIZE = 16

type CacheKey = tuple[uuid.UUID, str, int, datetime | None]
_cache: OrderedDict[CacheKey, list[RepertoireGame]] = OrderedDict()


class _MovesVisitor(chess.pgn.BaseVisitor[list[chess.Move] | None]):
    """Ходы основной линии без комментариев и вариантов; None — партия не с начальной позиции
    или не классические шахматы (в репертуар такие не входят)."""

    def __init__(self) -> None:
        self.moves: list[chess.Move] = []
        self.supported = True

    def visit_header(self, tagname: str, tagvalue: str) -> None:
        if tagname == "FEN" or (tagname == "Variant" and tagvalue != "Standard"):
            self.supported = False

    def begin_variation(self) -> chess.pgn.SkipType:
        return chess.pgn.SKIP

    def visit_comment(self, comment: str) -> None:
        return None

    def visit_move(self, board: chess.Board, move: chess.Move) -> None:
        if len(self.moves) < STORED_PLIES:
            self.moves.append(move)

    def result(self) -> list[chess.Move] | None:
        return self.moves if self.supported and self.moves else None


def parse_moves(pgn: str) -> list[chess.Move] | None:
    """Первые `STORED_PLIES` ходов партии из сохранённого PGN."""
    try:
        return chess.pgn.read_game(io.StringIO(pgn), Visitor=_MovesVisitor)
    except ValueError:
        return None


def _parse_all(
    color: Color, rows: Sequence[tuple[str, str, datetime | None, str | None, str | None]]
) -> list[RepertoireGame]:
    lines: list[RepertoireGame] = []
    for pgn, result, played_at, opening_name, opening_eco in rows:
        moves = parse_moves(pgn)
        if moves is None:
            continue
        line = game_line(
            moves,
            color.value,
            result,
            played_at,
            opening_name=opening_name,
            opening_eco=opening_eco,
        )
        if line is not None:
            lines.append(line)
    return lines


async def load_games(
    session: AsyncSession, user_id: uuid.UUID, color: Color
) -> list[RepertoireGame]:
    """Партии пользователя за цвет (без `user_color` не учитываются), разобранные и кэшированные."""
    filters = (Game.user_id == user_id, Game.user_color == color)
    count, newest = (
        await session.execute(select(func.count(), func.max(Game.created_at)).where(*filters))
    ).one()
    key: CacheKey = (user_id, color.value, count, newest)
    if (cached := _cache.get(key)) is not None:
        _cache.move_to_end(key)
        return cached
    rows = (
        await session.execute(
            select(Game.pgn, Game.result, Game.played_at, Game.opening_name, Game.opening_eco)
            .where(*filters)
            .order_by(Game.played_at.desc().nulls_last(), Game.id)
        )
    ).all()
    lines = await asyncio.to_thread(
        _parse_all,
        color,
        [(r.pgn, r.result, r.played_at, r.opening_name, r.opening_eco) for r in rows],
    )
    # Прежние записи того же пользователя и цвета устарели.
    for old in [k for k in _cache if k[:2] == key[:2]]:
        del _cache[old]
    _cache[key] = lines
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return lines


def clear_cache() -> None:
    _cache.clear()


async def repertoire_tree(
    session: AsyncSession, user_id: uuid.UUID, color: Color, *, max_ply: int, min_games: int
) -> RepertoireTree:
    games = await load_games(session, user_id, color)
    return build_tree(games, color.value, max_ply=max_ply, min_games=min_games)


async def repertoire_openings(
    session: AsyncSession, user_id: uuid.UUID, color: Color
) -> list[RepertoireOpening]:
    return opening_list(await load_games(session, user_id, color))
