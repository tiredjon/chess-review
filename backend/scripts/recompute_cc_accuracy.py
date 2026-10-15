"""Пересчитывает точность «как у Chess.com» (`analyses.cc_*_accuracy`) у готовых анализов по
сохранённым ходам — после первого внедрения и после смены параметров `cc_accuracy.PARAMS`.
Движок не нужен.

    PYTHONPATH=. uv run python scripts/recompute_cc_accuracy.py
"""

import asyncio

from sqlalchemy import select, update

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Move
from app.db.session import Database
from app.review.cc_accuracy import color_accuracy


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
            await session.execute(
                update(Analysis)
                .where(Analysis.id == analysis_id)
                .values(
                    cc_white_accuracy=color_accuracy(rows, white=True),
                    cc_black_accuracy=color_accuracy(rows, white=False),
                )
            )
        await session.commit()
        print(f"пересчитано анализов: {len(ids)}")
    await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
