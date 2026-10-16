"""ARQ-задача анализа партии: PGN из БД → pipeline → строки `moves` и точность в `analyses`.

Задача идемпотентна: при повторе (ARQ перезапускает задачи, прерванные остановкой
воркера) старые ходы анализа удаляются, уже готовый анализ не пересчитывается.
"""

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import delete, insert, update
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Move
from app.db.session import Database
from app.engine.analyzer import Analyzer, PositionEngine
from app.engine.cache import DbEvalCache
from app.importers.pgn import parse_game
from app.puzzles.generate import generate_puzzles
from app.review.pipeline import GameReview, analyse_game
from app.workers.progress import ProgressEvent, ProgressReporter, publish
from app.workers.serialize import accuracy_fields, move_row

log = structlog.get_logger(__name__)

TASK_NAME = "analyze_game"
ERROR_MAX_LEN = 500


def job_id(analysis_id: uuid.UUID) -> str:
    return f"analysis:{analysis_id}"


async def enqueue_analysis(arq: Any, analysis_id: uuid.UUID) -> None:
    """Ставит анализ в очередь ARQ; повторная постановка того же анализа игнорируется."""
    await arq.enqueue_job(TASK_NAME, str(analysis_id), _job_id=job_id(analysis_id))


async def analyze_game(ctx: dict[str, Any], analysis_id: str) -> str:
    """Задача ARQ. В `ctx`: settings, db, redis, engine (пул движков), engine_version."""
    settings: Settings = ctx["settings"]
    db: Database = ctx["db"]
    redis: Redis = ctx["redis"]
    engine: PositionEngine = ctx["engine"]
    analysis_uuid = uuid.UUID(analysis_id)
    log_ = log.bind(analysis_id=analysis_id)

    async with db.sessionmaker() as session:
        analysis = await session.get(Analysis, analysis_uuid, options=[selectinload(Analysis.game)])
        if analysis is None:
            log_.warning("analysis.missing")
            return "missing"
        if analysis.status == AnalysisStatus.DONE:
            # Повтор задачи, прерванной при генерации пазлов: она идемпотентна.
            await _generate_puzzles(ctx, analysis_uuid)
            return "done"
        await session.execute(delete(Move).where(Move.analysis_id == analysis_uuid))
        analysis.status = AnalysisStatus.RUNNING
        analysis.started_at = datetime.now(UTC)
        analysis.finished_at = None
        analysis.error = None
        analysis.engine_version = ctx["engine_version"]
        pgn, depth = analysis.game.pgn, analysis.depth
        await session.commit()

    log_.info("analysis.started", depth=depth)
    await publish(redis, analysis_uuid, ProgressEvent(status=AnalysisStatus.RUNNING))
    reporter = ProgressReporter(redis, analysis_uuid)
    try:
        game = parse_game(pgn)
        review = await analyse_game(
            Analyzer(engine, DbEvalCache(db.sessionmaker)),
            game.board(),
            list(game.mainline_moves()),
            depth=depth,
            multipv=settings.analysis_multipv,
            on_progress=reporter,
        )
        await reporter.flush()
        await _save_review(db, analysis_uuid, review)
    except asyncio.CancelledError:
        # Таймаут задачи или остановка воркера: без этого анализ навсегда остался бы running.
        reporter.cancel()
        await asyncio.shield(_fail(db, redis, analysis_uuid, "Анализ прерван"))
        raise
    except Exception as exc:
        log_.exception("analysis.failed")
        reporter.cancel()
        await _fail(db, redis, analysis_uuid, f"{type(exc).__name__}: {exc}")
        return "failed"

    await publish(
        redis,
        analysis_uuid,
        ProgressEvent(status=AnalysisStatus.DONE, done=reporter.total, total=reporter.total),
    )
    log_.info("analysis.done", moves=len(review.moves))
    await _generate_puzzles(ctx, analysis_uuid)
    return "done"


async def _generate_puzzles(ctx: dict[str, Any], analysis_id: uuid.UUID) -> None:
    """Пазлы из ошибок пользователя. Разбор уже сохранён и показан: сбой генерации только
    логируется, а отмена задачи (CancelledError) пробрасывается — ARQ повторит задачу."""
    db: Database = ctx["db"]
    analyser = Analyzer(ctx["engine"], DbEvalCache(db.sessionmaker))
    try:
        count = await generate_puzzles(db, analyser, analysis_id)
    except Exception:
        log.exception("puzzles.failed", analysis_id=str(analysis_id))
        return
    log.info("puzzles.generated", analysis_id=str(analysis_id), count=count)


async def _save_review(db: Database, analysis_id: uuid.UUID, review: GameReview) -> None:
    rows = [{**move_row(move), "analysis_id": analysis_id} for move in review.moves]
    async with db.sessionmaker() as session:
        if rows:
            await session.execute(insert(Move), rows)
        await session.execute(
            update(Analysis)
            .where(Analysis.id == analysis_id)
            .values(
                status=AnalysisStatus.DONE,
                finished_at=datetime.now(UTC),
                **accuracy_fields(review),
            )
        )
        await session.commit()


async def _fail(db: Database, redis: Redis, analysis_id: uuid.UUID, error: str) -> None:
    error = error[:ERROR_MAX_LEN]
    async with db.sessionmaker() as session:
        await session.execute(
            update(Analysis)
            .where(Analysis.id == analysis_id)
            .values(status=AnalysisStatus.FAILED, error=error, finished_at=datetime.now(UTC))
        )
        await session.commit()
    # Статус уже в БД; SSE-клиент без события увидит его при следующей проверке.
    with contextlib.suppress(Exception):
        await publish(redis, analysis_id, ProgressEvent(status=AnalysisStatus.FAILED, error=error))
