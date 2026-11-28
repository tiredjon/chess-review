"""API курсов и ARQ-задача сборки: каталог, создание (идемпотентность, очередь, лимит),
«Мои курсы», курс с деревом и идеями, удаление, изоляция; задача — статусы, прогресс, ошибки."""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import chess
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, text

from app.core.config import Settings
from app.core.rates import Rate
from app.courses.builder import course_key, parse_line
from app.courses.types import CourseTree, ModelGame
from app.db.models import Course, CourseStatus, TrainerCard, User
from app.db.session import Database
from app.workers import courses as course_worker
from app.workers import settings as worker_settings
from tests.conftest import api_client
from tests.course_fakes import ITALIAN, ITALIAN_GAMES, NAJDORF, FakeEngine, GamesExplorer

pytestmark = pytest.mark.integration

API = "/api/v1/courses"
OTHER = uuid.UUID("00000000-0000-0000-0000-0000000c0de5")


@pytest.fixture
async def cdb(db: Database) -> AsyncIterator[Database]:
    async def clean() -> None:
        async with db.engine.begin() as conn:
            for table in ("trainer_attempts", "trainer_cards", "user_courses", "courses"):
                await conn.execute(text(f"DELETE FROM {table}"))
            await conn.execute(text("DELETE FROM explorer_cache"))

    await clean()
    async with db.sessionmaker() as session:
        if await session.get(User, OTHER) is None:
            session.add(User(id=OTHER, email="courses-other@example.com"))
            await session.commit()
    yield db
    await clean()


@pytest.fixture
async def cclient(settings: Settings, cdb: Database, redis: Redis) -> AsyncIterator[AsyncClient]:
    async with api_client(settings) as client:
        yield client


def ctx(
    settings: Settings,
    db: Database,
    *,
    explorer: GamesExplorer | None = None,
    engine: FakeEngine | None = None,
) -> dict[str, Any]:
    small = settings.model_copy(update={"course_target_plies": 16, "course_max_nodes": 30})
    return {
        "settings": small,
        "db": db,
        "engine": engine or FakeEngine(),
        "explorer": explorer or GamesExplorer(ITALIAN_GAMES),
        "http": None,
    }


async def create(
    client: AsyncClient, line: str = ITALIAN, color: str = "white", **extra: Any
) -> Any:
    return await client.post(API, json={"line_uci": line.split(), "color": color, **extra})


async def course_row(db: Database, course_id: str) -> Course:
    async with db.sessionmaker() as session:
        course = await session.get(Course, uuid.UUID(course_id))
        assert course is not None
        return course


# --- каталог ---


async def test_catalog(cclient: AsyncClient) -> None:
    response = await cclient.get(f"{API}/catalog")
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert "max-age" in response.headers["cache-control"]
    families = response.json()["families"]
    sicilian = next(f for f in families if f.get("name") == "Sicilian Defense")
    assert any(v["name"] == "Najdorf Variation" for v in sicilian["variations"])

    etag = response.headers["etag"]
    cached = await cclient.get(f"{API}/catalog", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""

    plain = await cclient.get(f"{API}/catalog", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert plain.json() == response.json()


async def test_catalog_requires_login(settings: Settings, cdb: Database) -> None:
    async with api_client(settings, anonymous=True) as client:
        assert (await client.get(f"{API}/catalog")).status_code == 401


# --- создание ---


async def test_create_is_idempotent_and_queued(
    cclient: AsyncClient, cdb: Database, redis: Redis, settings: Settings
) -> None:
    response = await create(cclient)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["progress"] == 0
    assert body["name"] == "Italian Game"
    assert body["eco"] == "C50"
    assert body["line_san"] == ["e4", "e5", "Nf3", "Nc6", "Bc4"]
    assert body["source"] == "catalog"
    assert body["color"] == "white"
    assert await redis.exists(f"arq:job:course:{body['id']}")

    again = await create(cclient, name="Другое имя")
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]
    assert again.json()["name"] == "Italian Game"

    course = await course_row(cdb, body["id"])
    line = parse_line(ITALIAN.split())
    assert course.key == course_key(chess.WHITE, line)
    assert course.created_by == settings.default_user_id

    # Другой цвет — другой курс.
    black = await create(cclient, color="black")
    assert black.status_code == 202
    assert black.json()["id"] != body["id"]

    # Другой пользователь получает тот же курс в свои «Мои курсы», источник — свой.
    async with api_client(settings, OTHER) as other:
        mine = await create(other, source="repertoire")
        assert mine.status_code == 200
        assert mine.json()["id"] == body["id"]
        assert mine.json()["source"] == "repertoire"
        assert [c["id"] for c in (await other.get(API)).json()] == [body["id"]]


async def test_create_name_from_request(cclient: AsyncClient) -> None:
    response = await create(cclient, line="e2e4 c7c5 a2a3 h7h5", name="  Моя линия  ")
    assert response.status_code == 202
    assert response.json()["name"] == "Моя линия"


@pytest.mark.parametrize(
    ("line", "index"),
    [("e2e4 e2e4", 1), ("e2e5", 0), ("", None), ("g1f3 g8f6 f3g1 f6g8 " * 16, None)],
)
async def test_create_line_invalid(cclient: AsyncClient, line: str, index: int | None) -> None:
    response = await create(cclient, line=line)
    assert response.status_code == 422
    assert response.json()["code"] == "line_invalid"
    assert response.json()["params"].get("index") == index


async def test_create_bad_body(cclient: AsyncClient) -> None:
    response = await cclient.post(API, json={"line_uci": ["e2e4"], "color": "red"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_failed_course_is_requeued(cclient: AsyncClient, cdb: Database, redis: Redis) -> None:
    course_id = (await create(cclient)).json()["id"]
    async with cdb.sessionmaker() as session:
        course = await session.get(Course, uuid.UUID(course_id))
        assert course is not None
        course.status = CourseStatus.FAILED
        course.error_code = "explorer_unavailable"
        await session.commit()

    retried = await create(cclient)
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    assert retried.json()["error_code"] is None
    jobs = [k async for k in redis.scan_iter(f"arq:job:course:{course_id}:*")]
    assert len(jobs) == 1


async def test_rate_limit_only_for_new(settings: Settings, cdb: Database, redis: Redis) -> None:
    limited = settings.model_copy(
        update={"rate_limit_enabled": True, "rate_limit_course": Rate(1, 3600)}
    )
    async with api_client(limited) as client:
        assert (await create(client)).status_code == 202
        # Уже существующий курс лимит не тратит.
        assert (await create(client)).status_code == 200
        response = await create(client, color="black")
        assert response.status_code == 429
        assert response.json()["params"]["scope"] == "course"


async def test_enqueue_failure(
    cclient: AsyncClient, cdb: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*args: object, **kwargs: object) -> None:
        raise ConnectionError("redis")

    monkeypatch.setattr("app.api.courses.enqueue_course", broken)
    response = await create(cclient)
    assert response.status_code == 503
    assert response.json()["code"] == "queue_unavailable"
    async with cdb.sessionmaker() as session:
        course = await session.scalar(select(Course))
        assert course is not None
        assert course.status == CourseStatus.FAILED
        assert course.error_code == "enqueue_failed"


# --- чтение и удаление ---


async def test_list_get_and_build(cclient: AsyncClient, cdb: Database, settings: Settings) -> None:
    first = (await create(cclient, line=NAJDORF, color="black")).json()
    second = (await create(cclient)).json()
    listed = (await cclient.get(API)).json()
    assert [c["id"] for c in listed] == [second["id"], first["id"]]

    pending = await cclient.get(f"{API}/{second['id']}")
    assert pending.status_code == 200
    assert pending.json()["tree"] is None
    assert pending.json()["ideas_text"] == {}

    assert await course_worker.build_course(ctx(settings, cdb), second["id"]) == "ready"

    ready = (await cclient.get(f"{API}/{second['id']}")).json()
    assert ready["status"] == "ready"
    assert ready["progress"] == 100
    assert ready["built_at"] is not None
    tree = CourseTree.model_validate(ready["tree"])
    with_ideas = {str(n.id) for n in tree.nodes if n.ideas is not None}
    assert with_ideas
    assert set(ready["ideas_text"]) == with_ideas
    texts_ru = ready["ideas_text"]

    english = (await cclient.get(f"{API}/{second['id']}", params={"lang": "en"})).json()
    assert english["ideas_text"].keys() == texts_ru.keys()
    assert english["ideas_text"] != texts_ru
    assert (await cclient.get(f"{API}/{second['id']}", params={"lang": "de"})).status_code == 422


async def test_book_games_added_on_read(
    cclient: AsyncClient, cdb: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Партии книг не хранятся в дереве: API добавляет их при каждой выдаче курса
    (и выбрасывает книжные, если бы они оказались в сохранённом дереве)."""
    course_id = (await create(cclient)).json()["id"]
    assert await course_worker.build_course(ctx(settings, cdb), course_id) == "ready"
    async with cdb.sessionmaker() as session:
        course = await session.get(Course, uuid.UUID(course_id))
        assert course is not None
        assert course.tree is not None
        stored = CourseTree.model_validate(course.tree)
    assert all(g.source == "masters" for g in stored.model_games)
    book = ModelGame(
        id="book:lasker-1",
        node_id=stored.line_end,
        white="Tartakower",
        black="Burn",
        result="0-1",
        pgn="1. e4 e5 *",
        source="book",
        annotator="Edward Lasker",
        book="Chess Strategy (1915)",
    )
    seen: list[CourseTree] = []

    def fake(tree: CourseTree) -> list[ModelGame]:
        seen.append(tree)
        return [book]

    monkeypatch.setattr("app.api.courses.book_model_games", fake)
    for _ in range(2):
        games = (await cclient.get(f"{API}/{course_id}")).json()["tree"]["model_games"]
        assert [g["id"] for g in games] == [*(g.id for g in stored.model_games), "book:lasker-1"]
    assert games[-1]["annotator"] == "Edward Lasker"
    assert games[-1]["book"] == "Chess Strategy (1915)"
    assert len(seen) == 2


async def test_default_lang_is_users(
    cclient: AsyncClient, cdb: Database, settings: Settings
) -> None:
    course_id = (await create(cclient)).json()["id"]
    await course_worker.build_course(ctx(settings, cdb), course_id)
    ru = (await cclient.get(f"{API}/{course_id}")).json()["ideas_text"]
    async with cdb.sessionmaker() as session:
        user = await session.get(User, settings.default_user_id)
        assert user is not None
        user.lang = "en"
        await session.commit()
    try:
        default = (await cclient.get(f"{API}/{course_id}")).json()["ideas_text"]
        en = (await cclient.get(f"{API}/{course_id}", params={"lang": "en"})).json()["ideas_text"]
        assert default == en != ru
    finally:
        async with cdb.sessionmaker() as session:
            user = await session.get(User, settings.default_user_id)
            assert user is not None
            user.lang = "ru"
            await session.commit()


async def test_isolation_and_delete(
    cclient: AsyncClient, cdb: Database, settings: Settings
) -> None:
    course_id = (await create(cclient)).json()["id"]
    await course_worker.build_course(ctx(settings, cdb), course_id)

    async with api_client(settings, OTHER) as other:
        assert (await other.get(f"{API}/{course_id}")).status_code == 404
        assert (await other.delete(f"{API}/{course_id}")).status_code == 404
        assert (await other.get(API)).json() == []

    # Карточки тренажёра по курсу удаляются вместе с ним из «Моих курсов».
    started = await cclient.post(f"/api/v1/trainer/courses/{course_id}/start")
    assert started.status_code == 200
    assert started.json()["total"] > 0

    assert (await cclient.delete(f"{API}/{course_id}")).status_code == 204
    missing = await cclient.get(f"{API}/{course_id}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "course_not_found"
    assert (await cclient.delete(f"{API}/{course_id}")).status_code == 404
    assert (await cclient.get(API)).json() == []
    async with cdb.sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(TrainerCard)) == 0
        assert await session.get(Course, uuid.UUID(course_id)) is not None  # курс общий

    # Снова добавить — тот же готовый курс, без сборки.
    again = await create(cclient)
    assert again.status_code == 200
    assert again.json()["status"] == "ready"


async def test_unknown_course(cclient: AsyncClient) -> None:
    response = await cclient.get(f"{API}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["code"] == "course_not_found"
    assert (await cclient.get(f"{API}/not-a-uuid")).status_code == 422


# --- задача ---


async def test_task_statuses_and_progress(
    cclient: AsyncClient, cdb: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    course_id = (await create(cclient)).json()["id"]
    seen: list[tuple[CourseStatus, int]] = []
    original = course_worker._update

    async def spy(db: Database, cid: uuid.UUID, **values: Any) -> None:
        await original(db, cid, **values)
        row = await course_row(db, str(cid))
        seen.append((row.status, row.progress))

    monkeypatch.setattr(course_worker, "_update", spy)
    assert await course_worker.build_course(ctx(settings, cdb), course_id) == "ready"

    assert seen[-1] == (CourseStatus.READY, 100)
    building = [p for s, p in seen if s == CourseStatus.BUILDING]
    assert building
    assert building == sorted(building)
    assert building[-1] < 100
    course = await course_row(cdb, course_id)
    tree = CourseTree.model_validate(course.tree)
    assert len(tree.nodes) <= 30
    assert max(n.ply for n in tree.nodes) == 16
    assert course.error_code is None

    # Готовый курс повторно не собирается.
    engine = FakeEngine()
    assert await course_worker.build_course(ctx(settings, cdb, engine=engine), course_id) == "ready"
    assert engine.calls == 0


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"explorer": GamesExplorer([], fail=True)}, "explorer_unavailable"),
        ({"engine": FakeEngine(fail=True)}, "engine_unavailable"),
    ],
)
async def test_task_failures(
    cclient: AsyncClient,
    cdb: Database,
    settings: Settings,
    kwargs: dict[str, Any],
    code: str,
) -> None:
    course_id = (await create(cclient)).json()["id"]
    assert await course_worker.build_course(ctx(settings, cdb, **kwargs), course_id) == "failed"
    course = await course_row(cdb, course_id)
    assert course.status == CourseStatus.FAILED
    assert course.error_code == code
    assert course.tree is None
    shown = (await cclient.get(f"{API}/{course_id}")).json()
    assert shown["status"] == "failed"
    assert shown["error_code"] == code


async def test_task_timeout(cclient: AsyncClient, cdb: Database, settings: Settings) -> None:
    course_id = (await create(cclient)).json()["id"]
    context = ctx(settings, cdb, explorer=GamesExplorer(ITALIAN_GAMES, delay_s=0.2))
    context["settings"] = context["settings"].model_copy(update={"course_job_timeout_s": 0.05})
    assert await course_worker.build_course(context, course_id) == "failed"
    assert (await course_row(cdb, course_id)).error_code == "interrupted"


async def test_task_unexpected_error(
    cclient: AsyncClient, cdb: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    course_id = (await create(cclient)).json()["id"]

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("сломалось")

    monkeypatch.setattr("app.courses.builder.CourseBuilder.build", boom)
    assert await course_worker.build_course(ctx(settings, cdb), course_id) == "failed"
    assert (await course_row(cdb, course_id)).error_code == "internal"


async def test_task_missing_course(cdb: Database, settings: Settings) -> None:
    assert await course_worker.build_course(ctx(settings, cdb), str(uuid.uuid4())) == "missing"


async def test_task_creates_explorer_once(cdb: Database, settings: Settings) -> None:
    context: dict[str, Any] = {"settings": settings, "db": cdb, "http": object()}
    first = course_worker._explorer(context)
    assert course_worker._explorer(context) is first


def test_task_is_registered() -> None:
    functions = {f.name: f for f in worker_settings.WorkerSettings.functions}
    task = functions[course_worker.TASK_NAME]
    assert task.timeout_s is not None
    assert task.timeout_s > worker_settings.settings.course_job_timeout_s


def test_job_ids() -> None:
    course_id = uuid.uuid4()
    assert course_worker.job_id(course_id) == f"course:{course_id}"
    retry = course_worker.job_id(course_id, retry=True)
    assert retry.startswith(f"course:{course_id}:")
    assert retry != course_worker.job_id(course_id, retry=True)
