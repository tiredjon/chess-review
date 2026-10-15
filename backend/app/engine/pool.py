"""Пул процессов Stockfish (UCI): переиспользование, таймауты, перезапуск при падении."""

import asyncio
import contextlib
from collections.abc import Collection
from dataclasses import dataclass
from types import TracebackType
from typing import Self

import chess
import chess.engine
import structlog

from app.core.config import Settings
from app.review.types import EngineLine, PositionEval

log = structlog.get_logger(__name__)

# Сколько ждём корректного `quit` перед kill.
_QUIT_TIMEOUT_S = 2.0


class EngineError(Exception):
    """Анализ не удался даже после перезапуска движка."""


@dataclass(slots=True, eq=False)
class _Engine:
    transport: asyncio.SubprocessTransport
    protocol: chess.engine.UciProtocol

    @property
    def pid(self) -> int:
        return self.transport.get_pid()


class EnginePool:
    """N процессов движка; каждый анализ берёт свободный процесс из очереди.

    Слот, чей процесс упал или завис, помечается пустым (None) и запускается
    заново при следующем использовании — пул не теряет ёмкость.
    """

    def __init__(
        self,
        path: str,
        size: int,
        *,
        threads: int = 1,
        hash_mb: int = 128,
        timeout: float = 60.0,
        retries: int = 1,
    ) -> None:
        if size < 1:
            raise ValueError("size должен быть ≥ 1")
        self.path = path
        self.size = size
        self.threads = threads
        self.hash_mb = hash_mb
        self.timeout = timeout
        self.retries = retries
        self.version = "unknown"
        self._slots: asyncio.Queue[_Engine | None] = asyncio.Queue()
        self._engines: set[_Engine] = set()
        self._started = False

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(
            settings.stockfish_path,
            settings.engine_pool_size,
            threads=settings.engine_threads,
            hash_mb=settings.engine_hash_mb,
            timeout=settings.engine_timeout_s,
        )

    async def start(self) -> None:
        """Запускает все процессы сразу, чтобы ошибки конфигурации всплыли на старте."""
        if self._started:
            return
        engines = await asyncio.gather(*(self._spawn() for _ in range(self.size)))
        for engine in engines:
            self._slots.put_nowait(engine)
        self.version = engines[0].protocol.id.get("name", "unknown")
        self._started = True
        log.info("engine.pool.started", size=self.size, version=self.version)

    async def close(self) -> None:
        await asyncio.gather(*(self._stop(engine) for engine in list(self._engines)))
        self._slots = asyncio.Queue()
        self._started = False

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    @property
    def pids(self) -> list[int]:
        return [engine.pid for engine in self._engines]

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        exclude: Collection[chess.Move] = (),
    ) -> PositionEval:
        """Анализ позиции (должна быть не финальной). Оценки — за сторону на ходу.

        `exclude` — ходы, которые движок не рассматривает (поиск альтернатив).
        """
        if not self._started:
            raise RuntimeError("EnginePool не запущен")
        limit = chess.engine.Limit(depth=depth)
        root_moves = (
            [move for move in board.legal_moves if move not in exclude] if exclude else None
        )
        engine = await self._slots.get()
        try:
            for attempt in range(self.retries + 1):
                try:
                    if engine is None:
                        engine = await self._spawn()
                    infos = await asyncio.wait_for(
                        engine.protocol.analyse(
                            board, limit, multipv=multipv, root_moves=root_moves
                        ),
                        self.timeout,
                    )
                    return _to_position_eval(infos, depth)
                except (TimeoutError, chess.engine.EngineError, OSError) as exc:
                    log.warning(
                        "engine.failed",
                        attempt=attempt,
                        error=type(exc).__name__,
                        fen=board.fen(),
                    )
                    if engine is not None:
                        await self._stop(engine)
                        engine = None
            raise EngineError(f"движок не справился с позицией {board.fen()}")
        finally:
            self._slots.put_nowait(engine)

    async def _spawn(self) -> _Engine:
        transport, protocol = await chess.engine.popen_uci(self.path)
        engine = _Engine(transport, protocol)
        self._engines.add(engine)
        try:
            await protocol.configure({"Threads": self.threads, "Hash": self.hash_mb})
        except BaseException:
            await self._stop(engine)
            raise
        return engine

    async def _stop(self, engine: _Engine) -> None:
        self._engines.discard(engine)
        try:
            await asyncio.wait_for(engine.protocol.quit(), _QUIT_TIMEOUT_S)
        except (TimeoutError, chess.engine.EngineError, OSError):
            with contextlib.suppress(ProcessLookupError):
                engine.transport.kill()
        finally:
            engine.transport.close()


def _to_position_eval(infos: list[chess.engine.InfoDict], depth: int) -> PositionEval:
    lines = tuple(
        EngineLine(score=info["score"].relative, pv=tuple(info.get("pv", ())))
        for info in infos
        if "score" in info
    )
    if not lines:
        raise chess.engine.EngineError("движок не вернул оценку")
    return PositionEval(
        score=lines[0].score,
        lines=lines,
        depth=min((info.get("depth", depth) for info in infos), default=depth),
    )
