"""Генерация пазлов из готового анализа: воркер — сразу после анализа, бэкфилл —
`scripts/generate_puzzles.py`. Идемпотентно: пазл уникален по (пользователь, позиция),
повторная генерация или повторный анализ партии лишь обновляют ссылку на ход."""

import asyncio
import uuid

import chess
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Analysis, AnalysisStatus, Color, Game, Move, Puzzle
from app.db.session import Database
from app.puzzles.solution import PositionAnalyser, build_puzzle, is_source


async def generate_puzzles(db: Database, analyser: PositionAnalyser, analysis_id: uuid.UUID) -> int:
    """Пазлы из ошибок пользователя в анализе; возвращает число найденных (новых и уже
    бывших). Партии без цвета пользователя и неготовые анализы пропускаются."""
    async with db.sessionmaker() as session:
        row = (
            await session.execute(
                select(Analysis.status, Analysis.depth, Game.user_id, Game.user_color)
                .join(Game)
                .where(Analysis.id == analysis_id)
            )
        ).one_or_none()
        if row is None or row.status != AnalysisStatus.DONE or row.user_color is None:
            return 0
        moves = list(
            await session.scalars(
                select(Move).where(Move.analysis_id == analysis_id).order_by(Move.ply)
            )
        )

    player = chess.WHITE if row.user_color == Color.WHITE else chess.BLACK
    by_ply = {move.ply: move for move in moves}
    candidates = [
        move for move in moves if chess.Board(move.fen_before).turn == player and is_source(move)
    ]
    # Движок — вне сессии БД: позиции считаются параллельно (параллелизм ограничен пулом).
    drafts = await asyncio.gather(
        *(
            build_puzzle(move, by_ply.get(move.ply - 1), analyser, depth=row.depth)
            for move in candidates
        )
    )
    # Позиция может повториться в партии — один пазл на позицию (иначе ON CONFLICT
    # затронул бы одну строку дважды).
    rows = {
        draft.fen: {
            "user_id": row.user_id,
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
