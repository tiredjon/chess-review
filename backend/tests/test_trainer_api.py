"""API тренажёра: старт, очередь, ответы, сводка, ошибки, изоляция, лимит."""

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

import chess
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select, text, update

from app.core.config import Settings
from app.core.rates import Rate
from app.db.models import (
    Color,
    Course,
    CourseStatus,
    PositionEval,
    TrainerAttempt,
    TrainerCard,
    User,
    UserCourse,
)
from app.db.session import Database
from app.engine.cache import fen_key
from app.review.winprob import win_percent_from_cp
from tests.conftest import api_client
from tests.trainer_fakes import BrokenEngine, ScriptedEngine, build_tree

pytestmark = pytest.mark.integration

API = "/api/v1/trainer"
START_EPD = fen_key(chess.Board())


@pytest.fixture
async def tdb(db: Database) -> AsyncIterator[Database]:
    async def clean() -> None:
        async with db.engine.begin() as conn:
            for table in ("trainer_attempts", "trainer_cards", "user_courses", "courses"):
                await conn.execute(text(f"DELETE FROM {table}"))

    await clean()
    yield db
    await clean()


async def add_course(
    db: Database,
    owner: uuid.UUID | None,
    *,
    status: CourseStatus = CourseStatus.READY,
    color: str = "white",
) -> uuid.UUID:
    course = Course(
        key=uuid.uuid4().hex,
        color=Color(color),
        name=f"Курс {color}",
        line_uci=["e2e4"],
        status=status,
        tree=build_tree(color).model_dump(mode="json") if status == CourseStatus.READY else None,
        builder_version=1,
    )
    async with db.sessionmaker() as session:
        session.add(course)
        await session.flush()
        if owner is not None:
            session.add(UserCourse(user_id=owner, course_id=course.id, source="catalog"))
        await session.commit()
    return course.id


@pytest.fixture
async def course_id(tdb: Database, settings: Settings) -> uuid.UUID:
    return await add_course(tdb, settings.default_user_id)


def with_engine(engine: object) -> Callable[[FastAPI], None]:
    def setup(app: FastAPI) -> None:
        app.state.explore_engine = engine

    return setup


@pytest.fixture
def engine() -> ScriptedEngine:
    return ScriptedEngine()


@pytest.fixture
async def tclient(
    settings: Settings, tdb: Database, engine: ScriptedEngine
) -> AsyncIterator[AsyncClient]:
    async with api_client(settings, setup=with_engine(engine)) as client:
        yield client


async def start(client: AsyncClient, course_id: uuid.UUID) -> dict[str, object]:
    response = await client.post(f"{API}/courses/{course_id}/start")
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def answer(
    client: AsyncClient, course_id: uuid.UUID, node_id: int, uci: str, **extra: object
) -> dict[str, object]:
    response = await client.post(
        f"{API}/courses/{course_id}/nodes/{node_id}/answer", json={"uci": uci, **extra}
    )
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def test_start_creates_cards_idempotently(
    tclient: AsyncClient, tdb: Database, course_id: uuid.UUID
) -> None:
    first = await start(tclient, course_id)
    second = await start(tclient, course_id)

    assert first == {"course_id": str(course_id), "total": 3, "created": 3}
    assert second == {"course_id": str(course_id), "total": 3, "created": 0}
    async with tdb.sessionmaker() as session:
        cards = (await session.scalars(select(TrainerCard).order_by(TrainerCard.node_id))).all()
    assert [c.node_id for c in cards] == [0, 2, 3]
    assert cards[0].epd == START_EPD
    assert all(c.box == 0 and c.next_review_at is None for c in cards)


async def test_next_orders_new_cards_by_ply(tclient: AsyncClient, course_id: uuid.UUID) -> None:
    empty = await tclient.get(f"{API}/next", params={"course_id": str(course_id)})
    assert (empty.status_code, empty.json()) == (200, None)

    await start(tclient, course_id)
    first = (await tclient.get(f"{API}/next", params={"course_id": str(course_id)})).json()

    assert first == {
        "course_id": str(course_id),
        "node_id": 0,
        "fen": chess.Board().fen(),
        "path_uci": [],
        "color": "white",
        "box": 0,
        "due": False,
    }
    await answer(tclient, course_id, 0, "e2e4")
    second = (await tclient.get(f"{API}/next")).json()
    # Корень пройден (повтор через сутки); дальше — по порядку линии, при равном ply — по id.
    assert (second["node_id"], second["path_uci"]) == (2, ["e2e4", "e7e5"])


async def test_answer_main_alternative_wrong(
    tclient: AsyncClient, tdb: Database, course_id: uuid.UUID, engine: ScriptedEngine
) -> None:
    await start(tclient, course_id)
    root = chess.Board()
    # Лучшая в корне +50; d2d4 теряет около 3 п.п. (в пределах порога), h2h4 — много.
    for uci, cp in (("d2d4", 38), ("h2h4", -300)):
        after = root.copy()
        after.push_uci(uci)
        engine.scores[fen_key(after)] = -cp  # соперник на ходу: ученику +cp
    engine.scores[START_EPD] = 50

    main = await answer(tclient, course_id, 0, "e2e4")
    assert main["verdict"] == "main"
    assert main["expected"] == [{"uci": "e2e4", "san": "e4"}]
    assert (main["win_loss"], main["box"], main["ideas_node_id"]) == (None, 1, None)
    assert engine.calls == 0  # ход курса движок не трогает

    alt = await answer(tclient, course_id, 0, "d2d4")
    assert alt["verdict"] == "alternative"
    assert 0 <= alt["win_loss"] <= 5  # type: ignore[operator]
    assert alt["box"] == 1  # коробка не выросла

    wrong = await answer(tclient, course_id, 0, "h2h4", hint_used=False)
    assert wrong["verdict"] == "wrong"
    assert wrong["box"] == 0
    review_at = datetime.fromisoformat(str(wrong["next_review_at"]))
    assert timedelta(minutes=9) < review_at - datetime.now(UTC) <= timedelta(minutes=10)

    async with tdb.sessionmaker() as session:
        attempts = (await session.scalars(select(TrainerAttempt).order_by(TrainerAttempt.id))).all()
        card = await session.scalar(select(TrainerCard).where(TrainerCard.node_id == 0))
        studied = await session.scalar(select(UserCourse.last_studied_at))
    assert [(a.uci, a.verdict) for a in attempts] == [
        ("e2e4", "main"),
        ("d2d4", "alternative"),
        ("h2h4", "wrong"),
    ]
    assert card is not None
    assert (card.attempts, card.last_correct, card.box) == (3, False, 0)
    assert studied is not None


async def test_alternative_threshold_boundary(
    settings: Settings, tdb: Database, course_id: uuid.UUID
) -> None:
    """Потеря ровно на пороге — alternative, чуть выше порога — wrong."""
    after = chess.Board()
    after.push_uci("d2d4")
    engine = ScriptedEngine({START_EPD: 100, fen_key(after): 0})
    loss = win_percent_from_cp(100) - (100 - win_percent_from_cp(0))
    results = []
    for threshold in (loss, loss - 0.01):
        current = settings.model_copy(update={"course_alt_threshold": threshold})
        async with api_client(current, setup=with_engine(engine)) as client:
            await start(client, course_id)
            results.append((await answer(client, course_id, 0, "d2d4"))["verdict"])

    assert results == ["alternative", "wrong"]


async def test_hint_and_box_growth(tclient: AsyncClient, course_id: uuid.UUID) -> None:
    await start(tclient, course_id)

    first = await answer(tclient, course_id, 2, "g1f3")
    again = await answer(tclient, course_id, 2, "f1c4")  # второй ход курса — тоже main
    hinted = await answer(tclient, course_id, 2, "g1f3", hint_used=True)

    assert (first["box"], again["box"], hinted["box"]) == (1, 2, 2)
    assert first["ideas_node_id"] == 1
    assert (await answer(tclient, course_id, 3, "g1f3"))["ideas_node_id"] == 3


async def test_engine_results_are_cached(
    tclient: AsyncClient, tdb: Database, course_id: uuid.UUID, engine: ScriptedEngine
) -> None:
    await start(tclient, course_id)

    await answer(tclient, course_id, 0, "d2d4")
    calls = engine.calls
    await answer(tclient, course_id, 0, "d2d4")

    assert calls == 2  # позиция до хода и после
    assert engine.calls == calls
    async with tdb.sessionmaker() as session:
        cached = (await session.scalars(select(PositionEval))).all()
    assert len(cached) == 2
    assert {c.multipv for c in cached} == {1}


async def test_due_cards_come_before_new(
    tclient: AsyncClient, tdb: Database, course_id: uuid.UUID
) -> None:
    await start(tclient, course_id)
    now = datetime.now(UTC)
    async with tdb.sessionmaker() as session:
        for node_id, shift in ((3, -2), (2, -5)):  # узел 2 просрочен сильнее
            await session.execute(
                update(TrainerCard)
                .where(TrainerCard.node_id == node_id)
                .values(next_review_at=now + timedelta(hours=shift), box=2)
            )
        await session.commit()

    nxt = (await tclient.get(f"{API}/next", params={"course_id": str(course_id)})).json()
    assert (nxt["node_id"], nxt["due"], nxt["box"]) == (2, True, 2)

    # Ни просроченных, ни новых: все карточки на будущее — очередь пуста.
    async with tdb.sessionmaker() as session:
        await session.execute(update(TrainerCard).values(next_review_at=now + timedelta(days=3)))
        await session.commit()
    assert (await tclient.get(f"{API}/next")).json() is None


async def test_queue_across_courses_by_ply(
    tclient: AsyncClient, tdb: Database, settings: Settings, course_id: uuid.UUID
) -> None:
    second = await add_course(tdb, settings.default_user_id, color="black")
    await start(tclient, course_id)
    await start(tclient, second)

    # Первые две новые карточки — корни обоих курсов (ply 0); общая очередь не зависит от курса.
    seen = set()
    for _ in range(2):
        card = (await tclient.get(f"{API}/next")).json()
        seen.add((card["course_id"], card["node_id"]))
        await answer(tclient, uuid.UUID(card["course_id"]), card["node_id"], "e2e4")
    assert seen == {(str(course_id), 0), (str(second), 0)}


async def test_summary(tclient: AsyncClient, tdb: Database, course_id: uuid.UUID) -> None:
    assert (await tclient.get(f"{API}/summary")).json() == []
    await start(tclient, course_id)
    await answer(tclient, course_id, 2, "g1f3")
    async with tdb.sessionmaker() as session:
        await session.execute(
            update(TrainerCard)
            .where(TrainerCard.node_id == 3)
            .values(next_review_at=datetime.now(UTC) - timedelta(hours=1), box=3)
        )
        await session.commit()

    assert (await tclient.get(f"{API}/summary")).json() == [
        {
            "course_id": str(course_id),
            "name": "Курс white",
            "total": 3,
            "due": 1,
            "new": 1,
            "learned": 1,
        }
    ]


async def test_black_course_reports_color(
    tclient: AsyncClient, tdb: Database, settings: Settings
) -> None:
    cid = await add_course(tdb, settings.default_user_id, color="black")
    await start(tclient, cid)

    assert (await tclient.get(f"{API}/next", params={"course_id": str(cid)})).json()[
        "color"
    ] == "black"


async def test_errors(
    tclient: AsyncClient, tdb: Database, settings: Settings, course_id: uuid.UUID
) -> None:
    missing = uuid.uuid4()
    building = await add_course(tdb, settings.default_user_id, status=CourseStatus.BUILDING)
    await start(tclient, course_id)

    def code(response: object) -> tuple[int, str]:
        return response.status_code, response.json()["code"]  # type: ignore[attr-defined]

    assert code(await tclient.post(f"{API}/courses/{missing}/start")) == (404, "course_not_found")
    assert code(await tclient.get(f"{API}/next", params={"course_id": str(missing)})) == (
        404,
        "course_not_found",
    )
    assert code(await tclient.post(f"{API}/courses/{building}/start")) == (409, "course_not_ready")
    assert code(
        await tclient.post(f"{API}/courses/{building}/nodes/0/answer", json={"uci": "e2e4"})
    ) == (409, "course_not_ready")
    assert code(
        await tclient.post(f"{API}/courses/{missing}/nodes/0/answer", json={"uci": "e2e4"})
    ) == (404, "course_not_found")
    # Узел 1 — ход ученика, а не позиция перед ним; узла 99 нет вовсе.
    for node in (1, 99):
        assert code(
            await tclient.post(
                f"{API}/courses/{course_id}/nodes/{node}/answer", json={"uci": "e2e4"}
            )
        ) == (404, "trainer_card_not_found")
    for bad in ("e2e5", "xx", "e7e5", "e2e4e5e6"):
        assert code(
            await tclient.post(f"{API}/courses/{course_id}/nodes/0/answer", json={"uci": bad})
        ) == (422, "validation_error")
    # Ошибки ответов ничего не записывают.
    async with tdb.sessionmaker() as session:
        assert await session.scalar(select(TrainerAttempt.id)) is None


async def test_engine_unavailable(settings: Settings, tdb: Database, course_id: uuid.UUID) -> None:
    async with api_client(settings, setup=with_engine(BrokenEngine())) as client:
        await start(client, course_id)
        bad = await client.post(f"{API}/courses/{course_id}/nodes/0/answer", json={"uci": "d2d4"})
        # Ход курса движок не требует.
        good = await client.post(f"{API}/courses/{course_id}/nodes/0/answer", json={"uci": "e2e4"})

    assert (bad.status_code, bad.json()["code"]) == (503, "engine_unavailable")
    assert good.status_code == 200


async def test_user_isolation(
    tclient: AsyncClient, tdb: Database, settings: Settings, course_id: uuid.UUID
) -> None:
    await start(tclient, course_id)
    async with tdb.sessionmaker() as session:
        other = User(email=f"other-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(other)
        await session.commit()

    async with api_client(settings, other.id, setup=with_engine(ScriptedEngine())) as client:
        # Курс не в списке другого пользователя: старт и чужие карточки недоступны.
        denied = await client.post(f"{API}/courses/{course_id}/start")
        card = await client.post(f"{API}/courses/{course_id}/nodes/0/answer", json={"uci": "e2e4"})
        assert (denied.status_code, denied.json()["code"]) == (404, "course_not_found")
        assert (card.status_code, card.json()["code"]) == (404, "trainer_card_not_found")
        assert (await client.get(f"{API}/next")).json() is None
        assert (await client.get(f"{API}/summary")).json() == []

        # Добавил курс себе — карточки у него свои, прогресс владельца не затронут.
        async with tdb.sessionmaker() as session:
            session.add(UserCourse(user_id=other.id, course_id=course_id, source="catalog"))
            await session.commit()
        assert (await start(client, course_id))["created"] == 3
        await answer(client, course_id, 0, "e2e4")

    summary = (await tclient.get(f"{API}/summary")).json()
    assert [(s["total"], s["new"]) for s in summary] == [(3, 3)]


async def test_answer_rate_limit(
    settings: Settings, tdb: Database, course_id: uuid.UUID, redis: object
) -> None:
    limited = settings.model_copy(
        update={"rate_limit_enabled": True, "rate_limit_trainer": Rate(2, 3600)}
    )
    async with api_client(limited, setup=with_engine(ScriptedEngine())) as client:
        await start(client, course_id)
        codes = [
            (
                await client.post(f"{API}/courses/{course_id}/nodes/0/answer", json={"uci": "e2e4"})
            ).status_code
            for _ in range(3)
        ]
        # Остальные роуты тренажёра лимитом не затронуты.
        summary = await client.get(f"{API}/summary")

    assert codes == [200, 200, 429]
    assert summary.status_code == 200
