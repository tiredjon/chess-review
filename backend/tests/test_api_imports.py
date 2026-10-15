"""Импорт с Lichess / Chess.com: постановка в очередь, ARQ-задача (фейковые источники), статус."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, select, update

from app.api.deps import get_arq
from app.core.config import Settings
from app.db.models import Game, ImportJob, ImportStatus, User
from app.db.session import Database
from app.main import create_app
from app.workers.imports import import_games, job_id
from tests.import_fakes import FakeChessCom, FakeLichess, routed

pytestmark = pytest.mark.integration


@pytest.fixture
async def clean_user(db: Database, settings: Settings) -> AsyncIterator[None]:
    """Без импортов и ников у dev-пользователя (импорт запоминает ник)."""

    async def reset() -> None:
        async with db.sessionmaker() as session:
            await session.execute(delete(ImportJob))
            await session.execute(
                update(User)
                .where(User.id == settings.default_user_id)
                .values(lichess_username=None, chesscom_username=None)
            )
            await session.commit()

    await reset()
    yield
    await reset()


@pytest.fixture
def lichess() -> FakeLichess:
    return FakeLichess()


@pytest.fixture
def chesscom() -> FakeChessCom:
    return FakeChessCom()


@pytest.fixture
async def ctx(
    settings: Settings, db: Database, lichess: FakeLichess, chesscom: FakeChessCom
) -> AsyncIterator[dict[str, Any]]:
    """Контекст ARQ-задачи: фейковые Lichess и Chess.com, повторы без пауз."""
    fast = settings.model_copy(update={"import_rate_limit_wait_s": 0, "import_max_attempts": 2})
    transport = httpx.MockTransport(routed(lichess, chesscom))
    async with httpx.AsyncClient(transport=transport) as http:
        yield {"settings": fast, "db": db, "http": http}


async def start(client: AsyncClient, source: str, **body: object) -> dict[str, Any]:
    response = await client.post(f"/api/v1/imports/{source}", json=body)
    assert response.status_code == 202, response.text
    job: dict[str, Any] = response.json()
    return job


async def status_of(client: AsyncClient, job: dict[str, Any]) -> dict[str, Any]:
    response = await client.get(f"/api/v1/imports/{job['job_id']}")
    assert response.status_code == 200, response.text
    current: dict[str, Any] = response.json()
    return current


async def user_games(db: Database, settings: Settings) -> list[Game]:
    async with db.sessionmaker() as session:
        rows = await session.scalars(
            select(Game)
            .where(Game.user_id == settings.default_user_id)
            .order_by(Game.played_at.desc(), Game.external_id)
        )
        return list(rows)


@pytest.mark.usefixtures("clean_user")
async def test_import_enqueues_job_once(client: AsyncClient, redis: Redis) -> None:
    job = await start(client, "lichess", username="Alice", max=30)

    assert job["status"] == "queued"
    assert job["source"] == "lichess"
    assert job["username"] == "Alice"
    assert job["max_games"] == 30
    assert job["imported"] == 0
    assert await redis.exists(f"arq:job:{job_id(uuid.UUID(job['job_id']))}")

    # Тот же ник (без учёта регистра), пока импорт не закончен, — тот же импорт.
    again = await client.post("/api/v1/imports/lichess", json={"username": "alice"})
    assert again.status_code == 200
    assert again.json()["job_id"] == job["job_id"]

    # Другой ник или другая площадка — новый импорт; параметры по умолчанию.
    other = await start(client, "lichess", username="bob")
    chesscom = await start(client, "chesscom", username="alice")
    assert len({job["job_id"], other["job_id"], chesscom["job_id"]}) == 3
    assert other["max_games"] == 100
    assert chesscom["months"] == 3
    assert chesscom["max_games"] is None

    assert (await status_of(client, job))["status"] == "queued"


@pytest.mark.usefixtures("clean_user")
async def test_import_validates_input(client: AsyncClient) -> None:
    for source, body in [
        ("lichess", {"username": "a"}),
        ("lichess", {"username": "../etc"}),
        ("lichess", {"username": "alice", "max": 0}),
        ("lichess", {"username": "alice", "max": 1001}),
        ("chesscom", {"username": "al ice"}),
        ("chesscom", {"username": "alice", "months": 25}),
    ]:
        response = await client.post(f"/api/v1/imports/{source}", json=body)
        assert response.status_code == 422, (source, body)

    missing = await client.get(f"/api/v1/imports/{uuid.uuid4()}")
    assert missing.status_code == 404


@pytest.mark.usefixtures("clean_user")
async def test_lichess_import_saves_games_and_dedups(
    client: AsyncClient,
    db: Database,
    settings: Settings,
    ctx: dict[str, Any],
    lichess: FakeLichess,
) -> None:
    lichess.add_games("Alice", 5)
    rows = lichess.users["alice"]
    # Чёрными, вариант, партия без ходов.
    rows[1]["pgn"] = (
        rows[1]["pgn"]
        .replace('[White "Alice"]', '[White "x"]')
        .replace('[Black "opp1"]', '[Black "ALICE"]')
    )
    rows[2]["variant"] = "atomic"
    rows[3]["pgn"] = rows[3]["pgn"].replace("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6", "")
    job = await start(client, "lichess", username="alice", max=10)

    assert await import_games(ctx, job["job_id"]) == "done"

    done = await status_of(client, job)
    assert done["status"] == "done"
    assert (done["fetched"], done["imported"], done["skipped"]) == (5, 3, 2)
    assert done["started_at"] is not None
    assert done["finished_at"] is not None
    assert done["error"] is None
    games = await user_games(db, settings)
    assert {(g.external_id, g.user_color) for g in games} == {
        (rows[0]["id"], "white"),
        (rows[1]["id"], "black"),
        (rows[4]["id"], "white"),
    }
    assert all(g.source == "lichess" for g in games)
    assert all(g.opening_name == "Ruy Lopez: Morphy Defense" for g in games)
    listed = (await client.get("/api/v1/games", params={"source": "lichess"})).json()
    assert len(listed["items"]) == 3

    # Ник запомнен в профиле: по нему определяется цвет во вставленных PGN.
    async with db.sessionmaker() as session:
        user = await session.get(User, settings.default_user_id)
        assert user is not None
        assert user.lichess_username == "alice"
        assert user.chesscom_username is None

    # Повторный импорт: новых партий нет, дублей тоже.
    lichess.add_games("alice", 1, start_ms=1_800_000_000_000)
    lichess.users["alice"].sort(key=lambda g: -g["createdAt"])
    again = await start(client, "lichess", username="alice", max=10)
    assert await import_games(ctx, again["job_id"]) == "done"
    second = await status_of(client, again)
    assert (second["fetched"], second["imported"], second["skipped"]) == (6, 1, 2)
    assert len(await user_games(db, settings)) == 4


@pytest.mark.usefixtures("clean_user")
async def test_chesscom_import(
    client: AsyncClient,
    db: Database,
    settings: Settings,
    ctx: dict[str, Any],
    chesscom: FakeChessCom,
) -> None:
    now = datetime.now(UTC)
    chesscom.add_game("Bob", now.year, now.month, 1)
    chesscom.add_game("Bob", now.year, now.month, 2, white="opp", black="bob")
    chesscom.add_game("Bob", now.year, now.month, 3, rules="crazyhouse")
    chesscom.add_game("Bob", now.year - 3, 1, 4)  # за пределами окна
    job = await start(client, "chesscom", username="Bob", months=2)

    assert await import_games(ctx, job["job_id"]) == "done"

    done = await status_of(client, job)
    assert (done["fetched"], done["imported"], done["skipped"]) == (3, 2, 1)
    games = await user_games(db, settings)
    assert {(g.external_id, g.user_color, g.source) for g in games} == {
        ("live/1", "white", "chesscom"),
        ("live/2", "black", "chesscom"),
    }
    async with db.sessionmaker() as session:
        user = await session.get(User, settings.default_user_id)
        assert user is not None
        assert user.chesscom_username == "Bob"


@pytest.mark.usefixtures("clean_user")
async def test_import_keeps_existing_username(
    client: AsyncClient,
    db: Database,
    settings: Settings,
    ctx: dict[str, Any],
    lichess: FakeLichess,
) -> None:
    async with db.sessionmaker() as session:
        await session.execute(
            update(User).where(User.id == settings.default_user_id).values(lichess_username="me")
        )
        await session.commit()
    lichess.add_games("magnus", 1)
    job = await start(client, "lichess", username="magnus", max=1)

    assert await import_games(ctx, job["job_id"]) == "done"

    async with db.sessionmaker() as session:
        user = await session.get(User, settings.default_user_id)
        assert user is not None
        assert user.lichess_username == "me"
    (game,) = await user_games(db, settings)
    # Цвет — по нику, с которого импортировали.
    assert game.user_color == "white"


@pytest.mark.usefixtures("clean_user")
async def test_import_fails_with_readable_error(
    client: AsyncClient, ctx: dict[str, Any], lichess: FakeLichess
) -> None:
    missing = await start(client, "lichess", username="nobody")
    assert await import_games(ctx, missing["job_id"]) == "failed"
    failed = await status_of(client, missing)
    assert failed["status"] == "failed"
    assert failed["error"] == "Пользователь nobody не найден на Lichess"
    assert failed["finished_at"] is not None

    # Источник лежит: после всех попыток — failed, партии предыдущих страниц остаются.
    lichess.add_games("carol", 1)
    lichess.failures = [httpx.Response(503), httpx.Response(503)]
    down = await start(client, "lichess", username="carol")
    assert await import_games(ctx, down["job_id"]) == "failed"
    assert (await status_of(client, down))["error"] == "Lichess: ошибка сервера 503"

    # Неожиданная ошибка — тоже failed, с типом исключения.
    async def explode(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("boom")

    broken = await start(client, "chesscom", username="dave")
    async with httpx.AsyncClient(transport=httpx.MockTransport(explode)) as http:
        result = await import_games({**ctx, "http": http}, broken["job_id"])
    assert result == "failed"
    assert (await status_of(client, broken))["error"] == "RuntimeError: boom"

    # Готовый импорт и несуществующий не трогаются.
    assert await import_games(ctx, str(uuid.uuid4())) == "missing"


@pytest.mark.usefixtures("clean_user")
async def test_finished_import_is_not_rerun(
    client: AsyncClient, ctx: dict[str, Any], lichess: FakeLichess
) -> None:
    lichess.add_games("erin", 2)
    job = await start(client, "lichess", username="erin")
    assert await import_games(ctx, job["job_id"]) == "done"
    requests = len(lichess.requests)

    assert await import_games(ctx, job["job_id"]) == "done"

    assert len(lichess.requests) == requests
    # После завершения тот же ник можно импортировать снова.
    again = await start(client, "lichess", username="erin")
    assert again["job_id"] != job["job_id"]


@pytest.mark.usefixtures("clean_user")
async def test_queued_import_is_reenqueued(client: AsyncClient, db: Database, redis: Redis) -> None:
    job = await start(client, "chesscom", username="frank")
    await redis.flushdb()

    again = await client.post("/api/v1/imports/chesscom", json={"username": "frank"})

    assert again.status_code == 200
    assert await redis.exists(f"arq:job:{job_id(uuid.UUID(job['job_id']))}")
    # Идущий импорт заново в очередь не ставится.
    async with db.sessionmaker() as session:
        await session.execute(
            update(ImportJob)
            .where(ImportJob.id == uuid.UUID(job["job_id"]))
            .values(status=ImportStatus.RUNNING)
        )
        await session.commit()
    await redis.flushdb()
    running = await client.post("/api/v1/imports/chesscom", json={"username": "frank"})
    assert running.json()["status"] == "running"
    assert not await redis.exists(f"arq:job:{job_id(uuid.UUID(job['job_id']))}")


class BrokenQueue:
    async def enqueue_job(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("redis down")


@pytest.mark.usefixtures("clean_user")
async def test_import_reports_unavailable_queue(settings: Settings, db: Database) -> None:
    app = create_app(settings)
    app.dependency_overrides[get_arq] = BrokenQueue
    async with (
        LifespanManager(app) as manager,
        AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as ac,
    ):
        response = await ac.post("/api/v1/imports/lichess", json={"username": "gina"})

    assert response.status_code == 503
    async with db.sessionmaker() as session:
        (job,) = await session.scalars(select(ImportJob))
    assert job.status == ImportStatus.FAILED
    assert job.error == "Не удалось поставить импорт в очередь"
