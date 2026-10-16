"""Telegram-бот: `python -m app.bot` (сервис `bot` в compose, `make bot`).

Long polling (`getUpdates` с offset): каждое событие — отдельная задача, разборов
одновременно — `BOT_MAX_CONCURRENCY` (семафор в обработчике), анализ считает воркер.
SIGINT / SIGTERM — опрос останавливается, идущие ответы получают несколько секунд
на завершение, затем отменяются. Без `TELEGRAM_BOT_TOKEN` бот не запускается.
"""

import asyncio
import contextlib
import logging
import signal
import sys

import structlog
from arq.connections import ArqRedis
from redis.asyncio import ConnectionPool

from app.bot.handler import BotHandler
from app.bot.runner import QueueRunner
from app.bot.service import ReviewService
from app.bot.telegram import TelegramClient, TelegramError, Update
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import Database
from app.explain.llm import make_provider
from app.explain.service import Explainer
from app.importers.http import make_http_client

log = structlog.get_logger(__name__)

# Сколько ждать идущие ответы при остановке (docker stop даёт 10 с до SIGKILL).
SHUTDOWN_GRACE_S = 8.0
# Пауза после сбоя опроса (сеть, 5xx), если Telegram не назвал свою.
POLL_ERROR_WAIT_S = 5.0


async def poll(telegram: TelegramClient, handler: BotHandler, stop: asyncio.Event) -> None:
    """Цикл опроса до `stop`; события обрабатываются в фоне."""
    tasks: set[asyncio.Task[None]] = set()
    offset: int | None = None
    try:
        while not stop.is_set():
            updates = await _next_updates(telegram, offset, stop)
            for update in updates:
                offset = update.update_id + 1
                task = asyncio.create_task(handler.handle(update))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
    finally:
        if tasks:
            log.info("bot.draining", tasks=len(tasks))
            _, pending = await asyncio.wait(tasks, timeout=SHUTDOWN_GRACE_S)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        # Подтвердить обработанные события, чтобы после перезапуска они не пришли снова.
        if offset is not None:
            with contextlib.suppress(TelegramError):
                await telegram.get_updates(offset, poll_s=0)


async def _next_updates(
    telegram: TelegramClient, offset: int | None, stop: asyncio.Event
) -> list[Update]:
    """Следующая пачка событий; остановка прерывает long polling."""
    request = asyncio.create_task(telegram.get_updates(offset))
    stopped = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait({request, stopped}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stopped.cancel()
    if not request.done():
        request.cancel()
        await asyncio.gather(request, return_exceptions=True)
        return []
    try:
        return request.result()
    except TelegramError as exc:
        wait = float(exc.retry_after or POLL_ERROR_WAIT_S)
        log.warning("bot.poll_failed", error=exc.description, code=exc.error_code, wait_s=wait)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=wait)
        return []


async def run(settings: Settings) -> int:
    assert settings.telegram_bot_token is not None
    telegram = TelegramClient(
        settings.telegram_bot_token.get_secret_value(), api_url=settings.telegram_api_url
    )
    db = Database(settings.database_url)
    # ArqRedis — Redis с enqueue_job: очередь анализа, pubsub прогресса и лимиты.
    redis = ArqRedis(ConnectionPool.from_url(settings.redis_url))
    http = make_http_client(settings)
    llm = make_provider(settings)
    try:
        try:
            me = await telegram.get_me()
        except TelegramError as exc:
            log.error("bot.start_failed", error=exc.description, code=exc.error_code)
            return 1
        explainer = Explainer(llm, db.sessionmaker, concurrency=settings.llm_max_concurrency)
        service = ReviewService(settings, db, http, QueueRunner(redis, db), explainer)
        handler = BotHandler(settings, telegram, service, db, redis)

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        log.info(
            "bot.started", username=me.get("username"), concurrency=settings.bot_max_concurrency
        )
        await poll(telegram, handler, stop)
        log.info("bot.stopped")
        return 0
    finally:
        await telegram.aclose()
        await http.aclose()
        if llm is not None:
            await llm.close()
        await redis.aclose()
        await db.dispose()


def main() -> int:
    settings = get_settings()
    configure_logging(settings)
    # httpx пишет URL каждого запроса в INFO, а в URL Bot API — токен.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if settings.telegram_bot_token is None or not settings.telegram_bot_token.get_secret_value():
        print(
            "TELEGRAM_BOT_TOKEN не задан: получите токен у @BotFather и добавьте его в .env",
            file=sys.stderr,
        )
        return 2
    return asyncio.run(run(settings))


if __name__ == "__main__":
    sys.exit(main())
