"""Пазлы из уже готовых анализов (новые анализы получают пазлы в воркере сами).

Берётся последний готовый анализ каждой партии пользователя с известным цветом. Нужен
Stockfish (второй вариант для проверки однозначности); оценки кэшируются в `position_evals`,
поэтому повторный запуск быстрый. Идемпотентно.

    PYTHONPATH=. uv run python scripts/generate_puzzles.py
    docker compose exec worker python scripts/generate_puzzles.py
"""

import asyncio
import time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Game
from app.db.session import Database
from app.engine.analyzer import Analyzer
from app.engine.cache import DbEvalCache
from app.engine.pool import EnginePool
from app.puzzles.generate import generate_puzzles


async def main() -> None:
    settings = Settings()
    db = Database(settings.database_url)
    pool = EnginePool.from_settings(settings)
    await pool.start()
    try:
        async with db.sessionmaker() as session:
            ids = list(
                await session.scalars(
                    select(Analysis.id)
                    .join(Game)
                    .where(Analysis.status == AnalysisStatus.DONE, Game.user_color.is_not(None))
                    .order_by(Analysis.game_id, Analysis.created_at.desc(), Analysis.id)
                    .ext(distinct_on(Analysis.game_id))
                )
            )
        analyser = Analyzer(pool, DbEvalCache(db.sessionmaker))
        started, total = time.monotonic(), 0
        for number, analysis_id in enumerate(ids, 1):
            count = await generate_puzzles(db, analyser, analysis_id)
            total += count
            print(f"[{number}/{len(ids)}] анализ {analysis_id}: пазлов {count}", flush=True)
        print(f"готово: анализов {len(ids)}, пазлов {total}, {time.monotonic() - started:.0f} с")
    finally:
        await pool.close()
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
