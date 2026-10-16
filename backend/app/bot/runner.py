"""Запуск анализа и ожидание результата для бота.

В проде анализ считает воркер (очередь ARQ, как `POST /games/{id}/analyze`), бот ждёт
финального события в канале Redis `analysis:{id}:events` и на всякий случай
перепроверяет статус в БД. Тесты подставляют свой `AnalysisRunner` (задача воркера
прямо в процессе на фейковом движке).
"""

import uuid
from typing import Any, Protocol

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update

from app.core.errors import ErrorCode
from app.db.models import Analysis, AnalysisStatus
from app.db.session import Database
from app.workers.analysis import enqueue_analysis
from app.workers.progress import channel, parse_message

log = structlog.get_logger(__name__)

# Без событий статус перепроверяется в БД: событие могло потеряться (как в SSE).
STATUS_RECHECK_S = 5.0
FINAL = (AnalysisStatus.DONE, AnalysisStatus.FAILED)


class QueueUnavailableError(Exception):
    """Анализ не удалось поставить в очередь; он помечен failed."""


class AnalysisRunner(Protocol):
    async def run(self, analysis_id: uuid.UUID) -> None:
        """Запустить анализ (если он ещё не идёт) и дождаться done / failed.
        Таймаут — за вызывающим (отмена не трогает сам анализ в воркере)."""
        ...


class QueueRunner:
    """Анализ в воркере через очередь ARQ; `redis` — ArqRedis (enqueue + pubsub)."""

    def __init__(self, redis: Redis, db: Database) -> None:
        self.redis = redis
        self.db = db

    async def run(self, analysis_id: uuid.UUID) -> None:
        pubsub = self.redis.pubsub()
        # Подписка до постановки и проверки статуса: финальное событие не потеряется.
        await pubsub.subscribe(channel(analysis_id))
        try:
            await self._enqueue(analysis_id)
            status = await self._status(analysis_id)
            while status not in FINAL:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=STATUS_RECHECK_S
                )
                if message is None:
                    status = await self._status(analysis_id)
                elif parse_message(message).is_final:
                    return
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()  # type: ignore[no-untyped-call]

    async def _enqueue(self, analysis_id: uuid.UUID) -> None:
        # ARQ не дублирует задачу с тем же id: идущий анализ не запустится второй раз.
        arq: Any = self.redis
        try:
            await enqueue_analysis(arq, analysis_id)
        except Exception as exc:
            log.exception("bot.enqueue_failed", analysis_id=str(analysis_id))
            async with self.db.sessionmaker() as session:
                await session.execute(
                    update(Analysis)
                    .where(Analysis.id == analysis_id, Analysis.status == AnalysisStatus.QUEUED)
                    .values(
                        status=AnalysisStatus.FAILED,
                        error="Не удалось поставить анализ в очередь",
                        error_code=ErrorCode.ENQUEUE_FAILED,
                    )
                )
                await session.commit()
            raise QueueUnavailableError from exc

    async def _status(self, analysis_id: uuid.UUID) -> AnalysisStatus:
        async with self.db.sessionmaker() as session:
            status: AnalysisStatus | None = await session.scalar(
                select(Analysis.status).where(Analysis.id == analysis_id)
            )
        # Анализ удалён (вместе с партией) — ждать нечего.
        return AnalysisStatus.FAILED if status is None else status
