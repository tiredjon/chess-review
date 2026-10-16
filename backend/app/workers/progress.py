"""Прогресс анализа через Redis: воркер публикует, API отдаёт по SSE (`/analyses/{id}/events`).

Последнее состояние лежит в ключе (его читает клиент, подключившийся посреди анализа),
каждое изменение публикуется в канал. Финальные статусы (done/failed) тоже идут
в канал — по ним SSE-поток закрывается.
"""

import asyncio
import json
import uuid
from typing import Any

from pydantic import BaseModel
from redis.asyncio import Redis

from app.db.models import AnalysisStatus

# Ключ живёт дольше любого анализа, но не копится вечно.
PROGRESS_TTL_S = 3600


class ProgressEvent(BaseModel):
    status: AnalysisStatus
    # Проанализировано позиций из total (повторы позиций движок считает один раз).
    done: int = 0
    total: int = 0
    error: str | None = None
    # Код для интерфейса (`app/api/errors.py`), `error` — подробности.
    error_code: str | None = None

    @property
    def is_final(self) -> bool:
        return self.status in (AnalysisStatus.DONE, AnalysisStatus.FAILED)


def channel(analysis_id: uuid.UUID) -> str:
    return f"analysis:{analysis_id}:events"


def state_key(analysis_id: uuid.UUID) -> str:
    return f"analysis:{analysis_id}:progress"


async def publish(redis: Redis, analysis_id: uuid.UUID, event: ProgressEvent) -> None:
    payload = event.model_dump_json()
    await redis.set(state_key(analysis_id), payload, ex=PROGRESS_TTL_S)
    await redis.publish(channel(analysis_id), payload)


async def read_state(redis: Redis, analysis_id: uuid.UUID) -> ProgressEvent | None:
    raw = await redis.get(state_key(analysis_id))
    return None if raw is None else ProgressEvent.model_validate_json(raw)


def parse_message(message: dict[str, Any]) -> ProgressEvent:
    return ProgressEvent.model_validate(json.loads(message["data"]))


class ProgressReporter:
    """Синхронный колбэк `on_progress(done, total)` для анализатора → публикации в Redis.

    Публикации идут по одной в фоне; пока одна в полёте, промежуточные значения
    схлопываются в последнее — медленный Redis не тормозит движок.
    """

    def __init__(self, redis: Redis, analysis_id: uuid.UUID) -> None:
        self.redis = redis
        self.analysis_id = analysis_id
        self.total = 0
        self._latest: ProgressEvent | None = None
        self._task: asyncio.Task[None] | None = None

    def __call__(self, done: int, total: int) -> None:
        self.total = total
        self._latest = ProgressEvent(status=AnalysisStatus.RUNNING, done=done, total=total)
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._drain())

    async def _drain(self) -> None:
        while self._latest is not None:
            event, self._latest = self._latest, None
            await publish(self.redis, self.analysis_id, event)

    async def flush(self) -> None:
        """Дождаться отправки последнего значения."""
        if self._task is not None:
            await self._task

    def cancel(self) -> None:
        """Бросить неотправленное: после финального статуса «running» уже не нужен."""
        self._latest = None
        if self._task is not None:
            self._task.cancel()
