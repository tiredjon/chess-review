"""Анализ партий выборки (`python -m app.coach.norms analyze`): тот же конвейер, что у
пользователя (`analyse_game` + `save_review`, глубина и MultiPV по умолчанию), но без
Redis, очереди ARQ и пазлов. Партии берутся по кругу по группам (приоритетные первыми),
чтобы прерванный анализ оставлял равномерные частичные данные. Возобновляемо: незавершённый
анализ (`running` после остановки) пересчитывается, готовый — нет.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.coach.norms import PRIORITY_BANDS
from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Game, Move
from app.db.session import Database
from app.engine.analyzer import Analyzer, PositionEngine
from app.engine.cache import DbEvalCache
from app.importers.pgn import parse_game
from app.review.pipeline import analyse_game
from app.workers.analysis import save_review

log = structlog.get_logger(__name__)

# Порядок: только собираемые группы (`PRIORITY_BANDS`), сначала весь рапид, затем блиц; внутри —
# «волнами»: k-я партия каждого игрока по кругу групп, чтобы на группу быстрее набиралось
# игроков, а не партий.
_NEXT_SQL = """
WITH todo AS (
    SELECT s.game_id, s.time_class, s.center,
           row_number() OVER (PARTITION BY s.username ORDER BY s.game_id) AS k,
           dense_rank() OVER (PARTITION BY s.time_class, s.center ORDER BY s.username) AS p
    FROM norms_samples s
    WHERE s.center = ANY(:priority) AND NOT EXISTS (
        SELECT 1 FROM analyses a WHERE a.game_id = s.game_id AND a.status = 'done'
    )
)
SELECT game_id FROM todo
ORDER BY time_class <> 'rapid', k, p, center
LIMIT :limit
"""


async def pending_games(session: AsyncSession, limit: int) -> list[uuid.UUID]:
    rows = await session.execute(
        text(_NEXT_SQL),
        {"priority": list(PRIORITY_BANDS), "limit": limit},
    )
    return [row.game_id for row in rows]


async def _prepare(session: AsyncSession, game_id: uuid.UUID, depth: int) -> uuid.UUID:
    """Анализ партии: прежний незавершённый — заново, иначе новый."""
    analysis = await session.scalar(
        select(Analysis).where(Analysis.game_id == game_id).order_by(Analysis.created_at.desc())
    )
    if analysis is None:
        analysis = Analysis(game_id=game_id, depth=depth)
        session.add(analysis)
        await session.flush()
    await session.execute(delete(Move).where(Move.analysis_id == analysis.id))
    analysis.status = AnalysisStatus.RUNNING
    analysis.depth = depth
    analysis.started_at = datetime.now(UTC)
    await session.commit()
    return analysis.id


async def analyze_one(
    db: Database, engine: PositionEngine, settings: Settings, game_id: uuid.UUID
) -> bool:
    async with db.sessionmaker() as session:
        pgn = await session.scalar(select(Game.pgn).where(Game.id == game_id))
        if pgn is None:
            return False
        analysis_id = await _prepare(session, game_id, settings.analysis_depth)
    try:
        game = parse_game(pgn)
        review = await analyse_game(
            Analyzer(engine, DbEvalCache(db.sessionmaker)),
            game.board(),
            list(game.mainline_moves()),
            depth=settings.analysis_depth,
            multipv=settings.analysis_multipv,
        )
        await save_review(db, analysis_id, review)
    except Exception as exc:
        log.exception("norms.analyze.failed", game_id=str(game_id))
        async with db.sessionmaker() as session:
            await session.execute(
                update(Analysis)
                .where(Analysis.id == analysis_id)
                .values(status=AnalysisStatus.FAILED, error=str(exc)[:500])
            )
            await session.commit()
        return False
    return True


async def _run_batch(
    db: Database,
    engine: PositionEngine,
    settings: Settings,
    games: list[uuid.UUID],
    parallel: int,
) -> list[bool]:
    sem = asyncio.Semaphore(parallel)

    async def run(game_id: uuid.UUID) -> bool:
        async with sem:
            return await analyze_one(db, engine, settings, game_id)

    return list(await asyncio.gather(*(run(g) for g in games)))


async def analyze(
    db: Database,
    engine: PositionEngine,
    settings: Settings,
    *,
    parallel_games: int = 2,
    max_games: int | None = None,
    idle_wait_s: float = 60.0,
    follow: bool = False,
) -> int:
    """Анализирует партии выборки; `follow` — ждать новых, пока идёт сбор."""
    done = 0
    maker: async_sessionmaker[AsyncSession] = db.sessionmaker
    failed: set[uuid.UUID] = set()
    while max_games is None or done < max_games:
        async with maker() as session:
            batch = [g for g in await pending_games(session, 50) if g not in failed]
        if not batch:
            if not follow:
                break
            await asyncio.sleep(idle_wait_s)
            continue
        queue = batch[: parallel_games * 4]
        results = await _run_batch(db, engine, settings, queue, parallel_games)
        for game_id, ok in zip(queue, results, strict=True):
            if ok:
                done += 1
            else:
                failed.add(game_id)
        log.info("norms.analyze.progress", done=done, failed=len(failed))
    return done
