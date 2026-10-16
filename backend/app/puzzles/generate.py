"""Генерация пазлов из готового анализа: воркер — сразу после анализа, бэкфилл —
`scripts/generate_puzzles.py`. Идемпотентно: пазл уникален по (пользователь, позиция),
повторная генерация или повторный анализ партии лишь обновляют ссылку на ход."""

import asyncio
import uuid
from collections.abc import Collection
from dataclasses import dataclass

import chess
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Analysis, AnalysisStatus, Color, Game, Move, Puzzle
from app.db.session import Database
from app.engine.external import Probe, RecordingAnalyser
from app.puzzles.solution import PositionAnalyser, PuzzleDraft, build_puzzle, is_source


@dataclass(frozen=True, slots=True)
class _Source:
    user_id: uuid.UUID
    depth: int
    candidates: list[Move]
    by_ply: dict[int, Move]


async def _load_source(
    db: Database, analysis_id: uuid.UUID, skip_users: Collection[uuid.UUID] = ()
) -> _Source | None:
    """Ошибки пользователя в готовом анализе; None — анализ не готов, цвет неизвестен
    или партия пользователя из `skip_users`."""
    async with db.sessionmaker() as session:
        row = (
            await session.execute(
                select(Analysis.status, Analysis.depth, Game.user_id, Game.user_color)
                .join(Game)
                .where(Analysis.id == analysis_id)
            )
        ).one_or_none()
        if (
            row is None
            or row.status != AnalysisStatus.DONE
            or row.user_color is None
            or row.user_id in skip_users
        ):
            return None
        moves = list(
            await session.scalars(
                select(Move).where(Move.analysis_id == analysis_id).order_by(Move.ply)
            )
        )
    player = chess.WHITE if row.user_color == Color.WHITE else chess.BLACK
    return _Source(
        user_id=row.user_id,
        depth=row.depth,
        candidates=[
            move
            for move in moves
            if chess.Board(move.fen_before).turn == player and is_source(move)
        ],
        by_ply={move.ply: move for move in moves},
    )


async def _drafts(source: _Source, analyser: PositionAnalyser) -> list[PuzzleDraft | None]:
    # Движок — вне сессии БД: позиции считаются параллельно (параллелизм ограничен пулом).
    return await asyncio.gather(
        *(
            build_puzzle(move, source.by_ply.get(move.ply - 1), analyser, depth=source.depth)
            for move in source.candidates
        )
    )


async def collect_probes(db: Database, analysis_id: uuid.UUID) -> list[Probe]:
    """Позиции, которые генерация пазлов проверит движком, — для анализа из браузера:
    их считает браузер, затем `generate_puzzles` с `ProbeAnalyser`."""
    source = await _load_source(db, analysis_id)
    if source is None:
        return []
    recorder = RecordingAnalyser()
    await _drafts(source, recorder)
    return list(recorder.probes.values())


async def generate_puzzles(
    db: Database,
    analyser: PositionAnalyser,
    analysis_id: uuid.UUID,
    *,
    skip_users: Collection[uuid.UUID] = (),
) -> int:
    """Пазлы из ошибок пользователя в анализе; возвращает число найденных (новых и уже
    бывших). Партии без цвета пользователя, неготовые анализы и партии `skip_users`
    (системный пользователь Telegram-бота — его пазлы никто не решает) пропускаются."""
    source = await _load_source(db, analysis_id, skip_users)
    if source is None:
        return 0
    candidates = source.candidates
    drafts = await _drafts(source, analyser)
    # Позиция может повториться в партии — один пазл на позицию (иначе ON CONFLICT
    # затронул бы одну строку дважды).
    rows = {
        draft.fen: {
            "user_id": source.user_id,
            "move_id": move.id,
            "fen": draft.fen,
            "solution_uci": list(draft.solution),
            "themes": list(draft.themes),
        }
        for move, draft in zip(candidates, drafts, strict=True)
        if draft is not None
    }
    if rows:
        stmt = insert(Puzzle).values(list(rows.values()))
        stmt = stmt.on_conflict_do_update(
            constraint="uq_puzzles_user_id_fen", set_={"move_id": stmt.excluded.move_id}
        )
        async with db.sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()
    return len(rows)
