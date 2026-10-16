import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from arq.connections import ArqRedis
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import ConnectionPool

from app.api.errors import install_error_handlers
from app.api.health import router as health_router
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import Database
from app.explain.llm import make_provider

log = structlog.get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.db = Database(settings.database_url)
        # ArqRedis — тот же redis.asyncio.Redis плюс enqueue_job. Подключение ленивое:
        # без Redis API стартует, а /health/ready сообщает об ошибке.
        app.state.redis = ArqRedis(ConnectionPool.from_url(settings.redis_url))
        # None — LLM_PROVIDER=none: объяснения по шаблонам.
        app.state.llm = make_provider(settings)
        log.info("api.startup", env=settings.app_env)
        try:
            yield
        finally:
            await app.state.redis.aclose()
            if app.state.llm is not None:
                await app.state.llm.close()
            await app.state.db.dispose()
            log.info("api.shutdown")

    app = FastAPI(title="Chess Review API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Retry-After", "x-request-id"],
    )

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response

    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router)
    return app
