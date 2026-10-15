"""Кэш анализа позиций (SPEC §4.1): ключ — FEN без счётчиков ходов + depth + multipv."""

from typing import Any, Protocol

import chess
from chess.engine import Cp, Mate, Score
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import PositionEval as PositionEvalRow
from app.review.types import EngineLine, PositionEval


def fen_key(board: chess.Board) -> str:
    """FEN без счётчиков полуходов и ходов (взятие на проходе — только если возможно)."""
    return board.epd()


class EvalCache(Protocol):
    async def get(self, key: str, depth: int, multipv: int) -> PositionEval | None: ...

    async def put(self, key: str, depth: int, multipv: int, value: PositionEval) -> None: ...


class MemoryEvalCache:
    """Кэш в памяти процесса — для CLI и тестов."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, int, int], PositionEval] = {}

    def __len__(self) -> int:
        return len(self._data)

    async def get(self, key: str, depth: int, multipv: int) -> PositionEval | None:
        return self._data.get((key, depth, multipv))

    async def put(self, key: str, depth: int, multipv: int, value: PositionEval) -> None:
        self._data[(key, depth, multipv)] = value


class DbEvalCache:
    """Кэш в таблице `position_evals`."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def get(self, key: str, depth: int, multipv: int) -> PositionEval | None:
        async with self._sessionmaker() as session:
            row = await session.get(PositionEvalRow, (key, depth, multipv))
            return None if row is None else eval_from_data(row.data)

    async def put(self, key: str, depth: int, multipv: int, value: PositionEval) -> None:
        stmt = (
            insert(PositionEvalRow)
            .values(fen_key=key, depth=depth, multipv=multipv, data=eval_to_data(value))
            .on_conflict_do_nothing()
        )
        async with self._sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()


def _score_to_data(score: Score) -> dict[str, int]:
    mate = score.mate()
    if mate is None:
        cp = score.score()
        assert cp is not None
        return {"cp": cp}
    if mate == 0:
        # Финальные позиции не кэшируются: движок их не анализирует.
        raise ValueError("мат на доске не сериализуется")
    return {"mate": mate}


def _score_from_data(data: dict[str, Any]) -> Score:
    return Mate(data["mate"]) if "mate" in data else Cp(data["cp"])


def eval_to_data(value: PositionEval) -> dict[str, Any]:
    return {
        "depth": value.depth,
        "lines": [
            {**_score_to_data(line.score), "pv": [move.uci() for move in line.pv]}
            for line in value.lines
        ],
    }


def eval_from_data(data: dict[str, Any]) -> PositionEval:
    lines = tuple(
        EngineLine(
            score=_score_from_data(line),
            pv=tuple(chess.Move.from_uci(uci) for uci in line["pv"]),
        )
        for line in data["lines"]
    )
    return PositionEval(score=lines[0].score, lines=lines, depth=data["depth"])
