"""Пересчитывает точность «как у Chess.com» у готовых анализов по сохранённым ходам: общую
(`analyses.cc_*_accuracy`) и по фазам (`analyses.phase_accuracy`) — после смены формулы или
параметров `cc_accuracy.PARAMS`. Движок не нужен.

    PYTHONPATH=. uv run python scripts/recompute_cc_accuracy.py
"""

import asyncio

from sqlalchemy import select, update

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Move
from app.db.session import Database
from app.review.cc_accuracy import color_accuracy
from app.review.types import Phase


async def main() -> None:
    settings = Settings()
    db = Database(settings.database_url)
    async with db.sessionmaker() as session:
        ids = list(
            await session.scalars(select(Analysis.id).where(Analysis.status == AnalysisStatus.DONE))
        )
        for analysis_id in ids:
            moves = list(
                await session.scalars(
                    select(Move).where(Move.analysis_id == analysis_id).order_by(Move.ply)
                )
            )
            rows = [
                (
                    m.fen_before.split()[1] == "w",
                    m.eval_before_cp,
                    m.mate_before,
                    m.eval_after_cp,
                    m.mate_after,
                )
                for m in moves
            ]
            by_phase = {
                phase: [row for row, m in zip(rows, moves, strict=True) if m.phase == phase]
                for phase in Phase
            }
            phase_accuracy = {
                color: {
                    phase.value: color_accuracy(phase_rows, white=color == "white")
                    for phase, phase_rows in by_phase.items()
                }
                for color in ("white", "black")
            }
            await session.execute(
                update(Analysis)
                .where(Analysis.id == analysis_id)
                .values(
                    cc_white_accuracy=color_accuracy(rows, white=True),
                    cc_black_accuracy=color_accuracy(rows, white=False),
                    phase_accuracy=phase_accuracy,
                )
            )
        await session.commit()
        print(f"пересчитано анализов: {len(ids)}")
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
