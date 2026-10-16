"""Анализ партии: постановка в очередь, ARQ-задача, результат в API, SSE-прогресс."""

import asyncio
import json
import uuid
from collections.abc import Collection
from pathlib import Path
from typing import Any

import chess
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, update

from app.api import analyses as analyses_api
from app.api.deps import get_arq
from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Game, Move
from app.db.models import PositionEval as PositionEvalRow
from app.db.session import Database
from app.engine.pool import EnginePool
from app.review.types import PositionEval
from app.workers.analysis import analyze_game, job_id
from app.workers.progress import ProgressEvent, channel, publish
from tests.conftest import api_client
from tests.test_analyzer import FakeEngine

pytestmark = pytest.mark.integration

DATA = Path(__file__).parent / "data"
OPERA = (DATA / "opera_game.pgn").read_text(encoding="utf-8")


@pytest.fixture
async def game_id(client: AsyncClient, db: Database) -> str:
    response = await client.post("/api/v1/games/pgn", json={"pgn": OPERA})
    game_id: str = response.json()[0]["id"]
    return game_id


@pytest.fixture
def ctx(settings: Settings, db: Database, redis: Redis) -> dict[str, Any]:
    """Контекст ARQ-задачи с фейковым движком."""
    return {
        "settings": settings,
        "db": db,
        "redis": redis,
        "engine": FakeEngine(),
        "engine_version": "Fake 1.0",
    }


async def start_analysis(client: AsyncClient, game_id: str, depth: int = 6) -> dict[str, Any]:
    response = await client.post(f"/api/v1/games/{game_id}/analyze", json={"depth": depth})
    assert response.status_code == 202, response.text
    analysis: dict[str, Any] = response.json()
    return analysis


def parse_sse(body: str) -> list[dict[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        assert lines["event"] == "progress"
        events.append(json.loads(lines["data"]))
    return events


async def test_analyze_enqueues_job_once(
    client: AsyncClient, game_id: str, redis: Redis, settings: Settings
) -> None:
    analysis = await start_analysis(client, game_id)

    assert analysis["status"] == "queued"
    assert analysis["game_id"] == game_id
    assert analysis["depth"] == 6
    assert analysis["moves"] == []
    assert await redis.exists(f"arq:job:{job_id(uuid.UUID(analysis['id']))}")

    # Повтор той же глубины — тот же анализ; другая глубина — новый.
    again = await client.post(f"/api/v1/games/{game_id}/analyze", json={"depth": 6})
    assert again.status_code == 200
    assert again.json()["id"] == analysis["id"]
    other = await start_analysis(client, game_id, depth=8)
    assert other["id"] != analysis["id"]

    # Без тела — глубина из настроек.
    default = await client.post(f"/api/v1/games/{game_id}/analyze")
    assert default.status_code == 202
    assert default.json()["depth"] == settings.analysis_depth

    detail = (await client.get(f"/api/v1/games/{game_id}")).json()
    assert detail["analysis"]["id"] == default.json()["id"]
    listed = (await client.get("/api/v1/games")).json()["items"][0]
    assert listed["analysis"]["status"] == "queued"


async def test_analyze_validates_input(client: AsyncClient, game_id: str) -> None:
    bad_depth = await client.post(f"/api/v1/games/{game_id}/analyze", json={"depth": 0})
    missing = await client.post(f"/api/v1/games/{uuid.uuid4()}/analyze", json={})
    missing_analysis = await client.get(f"/api/v1/analyses/{uuid.uuid4()}")
    missing_events = await client.get(f"/api/v1/analyses/{uuid.uuid4()}/events")

    assert bad_depth.status_code == 422
    assert missing.status_code == 404
    assert missing_analysis.status_code == 404
    assert missing_events.status_code == 404


class BrokenQueue:
    async def enqueue_job(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("redis down")


async def test_analyze_reports_unavailable_queue(
    settings: Settings, db: Database, game_id: str
) -> None:
    def setup(app: FastAPI) -> None:
        app.dependency_overrides[get_arq] = BrokenQueue

    async with api_client(settings, setup=setup) as ac:
        response = await ac.post(f"/api/v1/games/{game_id}/analyze", json={"depth": 6})

    assert response.status_code == 503
    async with db.sessionmaker() as session:
        analysis = await session.scalar(select(Analysis).where(Analysis.game_id == game_id))
    assert analysis is not None
    assert analysis.status == AnalysisStatus.FAILED


async def test_worker_saves_review(
    client: AsyncClient, game_id: str, ctx: dict[str, Any], redis: Redis
) -> None:
    analysis = await start_analysis(client, game_id)

    assert await analyze_game(ctx, analysis["id"]) == "done"

    response = await client.get(f"/api/v1/analyses/{analysis['id']}")
    result = response.json()
    assert result["status"] == "done"
    assert result["engine_version"] == "Fake 1.0"
    assert result["started_at"] is not None
    assert result["finished_at"] is not None
    assert result["white_accuracy"] is not None
    assert 0 <= result["cc_white_accuracy"] <= 100
    assert 0 <= result["cc_black_accuracy"] <= 100
    assert set(result["phase_accuracy"]) == {"white", "black"}
    assert result["progress"] is None

    moves = result["moves"]
    assert len(moves) == 33
    first, last = moves[0], moves[-1]
    assert (first["ply"], first["fullmove"], first["color"], first["san"]) == (1, 1, "white", "e4")
    assert first["class"] == "book"
    assert (last["san"], last["fullmove"], last["color"]) == ("Rd8#", 17, "white")
    assert last["mate_after"] == 0
    assert last["reply_pv"] is None
    assert moves[31]["class"] == "forced"  # 16… Nxb8
    assert {"played", "missed", "refutation", "sacrifice"} <= set(first["motifs"])
    assert first["pv"][0].keys() == {"uci", "san"}

    # Карточка партии отдаёт тот же анализ с ходами.
    detail = (await client.get(f"/api/v1/games/{game_id}")).json()
    assert detail["analysis"]["id"] == analysis["id"]
    assert len(detail["analysis"]["moves"]) == 33

    # Повторный запуск задачи (ретрай ARQ) готовый анализ не трогает.
    assert await analyze_game(ctx, analysis["id"]) == "done"
    async with ctx["db"].sessionmaker() as session:
        count = await session.scalar(
            select(func.count()).select_from(Move).where(Move.analysis_id == analysis["id"])
        )
    assert count == 33

    # Готовый анализ той же глубины не перезапускается.
    again = await client.post(f"/api/v1/games/{game_id}/analyze", json={"depth": 6})
    assert again.status_code == 200
    assert again.json()["status"] == "done"
    assert len(again.json()["moves"]) == 33

    # Последнее событие прогресса — done со счётчиками.
    events = parse_sse((await client.get(f"/api/v1/analyses/{analysis['id']}/events")).text)
    assert len(events) == 1
    assert events[0]["status"] == "done"
    assert events[0]["done"] == events[0]["total"] > 0


async def test_worker_retry_replaces_partial_moves(
    client: AsyncClient, game_id: str, ctx: dict[str, Any]
) -> None:
    analysis = await start_analysis(client, game_id)
    assert await analyze_game(ctx, analysis["id"]) == "done"
    # Как будто воркер упал посреди сохранения: статус running, ходы частично есть.
    async with ctx["db"].sessionmaker() as session:
        await session.execute(
            update(Analysis)
            .where(Analysis.id == analysis["id"])
            .values(status=AnalysisStatus.RUNNING)
        )
        await session.commit()

    assert await analyze_game(ctx, analysis["id"]) == "done"
    result = (await client.get(f"/api/v1/analyses/{analysis['id']}")).json()
    assert len(result["moves"]) == 33


async def test_worker_marks_failure(client: AsyncClient, game_id: str, ctx: dict[str, Any]) -> None:
    analysis = await start_analysis(client, game_id)
    async with ctx["db"].sessionmaker() as session:
        await session.execute(update(Game).where(Game.id == game_id).values(pgn="испорчено"))
        await session.commit()

    assert await analyze_game(ctx, analysis["id"]) == "failed"

    result = (await client.get(f"/api/v1/analyses/{analysis['id']}")).json()
    assert result["status"] == "failed"
    assert "PgnError" in result["error"]
    assert result["moves"] == []
    events = parse_sse((await client.get(f"/api/v1/analyses/{analysis['id']}/events")).text)
    assert [e["status"] for e in events] == ["failed"]
    assert "PgnError" in events[0]["error"]
    # Упавший анализ можно перезапустить.
    assert (await start_analysis(client, game_id))["id"] != analysis["id"]


async def test_worker_ignores_missing_analysis(ctx: dict[str, Any]) -> None:
    assert await analyze_game(ctx, str(uuid.uuid4())) == "missing"


class HangingEngine(FakeEngine):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        exclude: Collection[chess.Move] = (),
    ) -> PositionEval:
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


async def test_cancelled_job_marks_analysis_failed(
    client: AsyncClient, game_id: str, ctx: dict[str, Any]
) -> None:
    analysis = await start_analysis(client, game_id)
    engine = ctx["engine"] = HangingEngine()

    task = asyncio.create_task(analyze_game(ctx, analysis["id"]))
    await asyncio.wait_for(engine.started.wait(), 5)
    running = (await client.get(f"/api/v1/analyses/{analysis['id']}")).json()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert running["status"] == "running"
    result = (await client.get(f"/api/v1/analyses/{analysis['id']}")).json()
    assert result["status"] == "failed"
    assert result["error"] == "Анализ прерван"
    assert result["error_code"] == "interrupted"


async def _wait_for_subscriber(redis: Redis, name: str) -> None:
    for _ in range(200):
        [(_, count)] = await redis.pubsub_numsub(name)
        if count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("SSE-клиент не подписался")


@pytest.fixture
def snapshot_taken(monkeypatch: pytest.MonkeyPatch) -> asyncio.Event:
    """Событие «поток SSE снял первый снимок состояния». «Воркер» в тестах продолжает
    только после него: иначе на медленной машине (CI) он успевал завершить анализ раньше
    снимка, и поток закрывался первым же событием."""
    taken = asyncio.Event()
    current_event = analyses_api._current_event

    async def watched(*args: Any) -> ProgressEvent:
        event = await current_event(*args)
        taken.set()
        return event

    monkeypatch.setattr(analyses_api, "_current_event", watched)
    return taken


async def test_events_stream_progress(
    client: AsyncClient, game_id: str, redis: Redis, db: Database, snapshot_taken: asyncio.Event
) -> None:
    analysis = await start_analysis(client, game_id)
    analysis_id = uuid.UUID(analysis["id"])
    await publish(
        redis, analysis_id, ProgressEvent(status=AnalysisStatus.RUNNING, done=1, total=30)
    )

    async def worker() -> None:
        await _wait_for_subscriber(redis, channel(analysis_id))
        await snapshot_taken.wait()
        await publish(
            redis, analysis_id, ProgressEvent(status=AnalysisStatus.RUNNING, done=15, total=30)
        )
        async with db.sessionmaker() as session:
            await session.execute(
                update(Analysis)
                .where(Analysis.id == analysis_id)
                .values(status=AnalysisStatus.DONE)
            )
            await session.commit()
        await publish(
            redis, analysis_id, ProgressEvent(status=AnalysisStatus.DONE, done=30, total=30)
        )

    publisher = asyncio.create_task(worker())
    # Клиент, пришедший посреди анализа, сразу видит последнее состояние.
    polled = (await client.get(f"/api/v1/analyses/{analysis_id}")).json()
    response = await client.get(f"/api/v1/analyses/{analysis_id}/events")
    await publisher

    assert polled["progress"] == {"done": 1, "total": 30}
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [(e["status"], e["done"]) for e in parse_sse(response.text)]
    # Первое событие — снимок: статус из БД, счётчики из Redis. Подписка идёт раньше
    # снимка, поэтому он может уже включать следующее событие (тогда оно придёт дважды).
    assert events[0] in {("queued", 1), ("queued", 15)}
    assert events[1:] == [("running", 15), ("done", 30)]


async def test_events_recheck_database_when_event_is_lost(
    client: AsyncClient,
    game_id: str,
    redis: Redis,
    db: Database,
    *,
    monkeypatch: pytest.MonkeyPatch,
    snapshot_taken: asyncio.Event,
) -> None:
    monkeypatch.setattr(analyses_api, "STATUS_RECHECK_S", 0.05)
    analysis = await start_analysis(client, game_id)
    analysis_id = uuid.UUID(analysis["id"])

    async def crash() -> None:
        await _wait_for_subscriber(redis, channel(analysis_id))
        await snapshot_taken.wait()
        # Воркер пометил анализ упавшим, но событие в Redis не дошло.
        async with db.sessionmaker() as session:
            await session.execute(
                update(Analysis)
                .where(Analysis.id == analysis_id)
                .values(status=AnalysisStatus.FAILED, error="boom", error_code="internal")
            )
            await session.commit()

    crasher = asyncio.create_task(crash())
    response = await client.get(f"/api/v1/analyses/{analysis_id}/events")
    await crasher

    events = parse_sse(response.text)
    assert [e["status"] for e in events] == ["queued", "failed"]
    assert events[-1]["error"] == "boom"
    assert events[-1]["error_code"] == "internal"


async def test_worker_with_stockfish(
    client: AsyncClient,
    game_id: str,
    ctx: dict[str, Any],
    stockfish_path: str,
) -> None:
    analysis = await start_analysis(client, game_id, depth=8)
    async with EnginePool(stockfish_path, 2) as pool:
        ctx["engine"], ctx["engine_version"] = pool, pool.version
        assert await analyze_game(ctx, analysis["id"]) == "done"

    result = (await client.get(f"/api/v1/analyses/{analysis['id']}")).json()
    assert result["engine_version"].startswith("Stockfish")
    assert result["white_accuracy"] > result["black_accuracy"]
    moves = result["moves"]
    last = moves[-1]
    assert last["san"] == "Rd8#"
    assert last["mate_after"] == 0
    assert last["class"] in {"best", "great"}
    assert {m["type"] for m in last["motifs"]["played"]} == {"mate_in_n", "back_rank"}
    # Оценки движка закэшированы.
    async with ctx["db"].sessionmaker() as session:
        cached = await session.scalar(select(func.count()).select_from(PositionEvalRow))
    assert cached is not None
    assert cached > 0
