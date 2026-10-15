"""API объяснений: ход, пакет по анализу, общий разбор партии."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update

from app.core.config import Settings
from app.db.models import (
    Analysis,
    AnalysisStatus,
    Color,
    Explanation,
    Game,
    GameSource,
    Move,
    User,
)
from app.db.session import Database
from app.main import create_app
from app.review.types import MoveClass, Phase
from tests.explain_data import REVIEW
from tests.test_explain_service import FakeLLM

pytestmark = pytest.mark.integration


async def insert_review(
    db: Database, user_id: uuid.UUID, status: AnalysisStatus = AnalysisStatus.DONE
) -> tuple[uuid.UUID, dict[str, int]]:
    """Партия с готовым анализом Оперной партии; возвращает id анализа и id ходов по SAN."""
    async with db.sessionmaker() as session:
        game = Game(
            user_id=user_id,
            source=GameSource.PGN,
            external_id=uuid.uuid4().hex,
            pgn="",
            white="Paul Morphy",
            black="Duke Karl / Count Isouard",
            result="1-0",
            opening_name="Philidor Defense",
            user_color=Color.BLACK,
        )
        session.add(game)
        await session.flush()
        analysis = Analysis(
            game_id=game.id,
            depth=14,
            status=status,
            white_accuracy=REVIEW["white_accuracy"],
            black_accuracy=REVIEW["black_accuracy"],
            phase_accuracy=REVIEW["phase_accuracy"],
        )
        session.add(analysis)
        await session.flush()
        for row in REVIEW["moves"]:
            session.add(
                Move(
                    **{
                        **row,
                        "move_class": MoveClass(row["move_class"]),
                        "phase": Phase(row["phase"]),
                    },
                    analysis_id=analysis.id,
                )
            )
        await session.commit()
        moves = await session.execute(
            select(Move.san, Move.id).where(Move.analysis_id == analysis.id).order_by(Move.ply)
        )
        # Первый ход с таким SAN.
        ids: dict[str, int] = {}
        for san, move_id in moves:
            ids.setdefault(san, move_id)
        return analysis.id, ids


@pytest.fixture
async def review(
    client: AsyncClient, db: Database, settings: Settings
) -> AsyncIterator[tuple[uuid.UUID, dict[str, int]]]:
    async with db.sessionmaker() as session:
        await session.execute(delete(Explanation))
        await session.commit()
    yield await insert_review(db, settings.default_user_id)
    async with db.sessionmaker() as session:
        await session.execute(delete(Explanation))
        await session.execute(
            update(User).where(User.id == settings.default_user_id).values(lang="ru")
        )
        await session.commit()


@asynccontextmanager
async def llm_client(settings: Settings, llm: FakeLLM) -> AsyncIterator[AsyncClient]:
    """Клиент API, у которого провайдер LLM подменён фейком."""
    app = create_app(settings)
    async with LifespanManager(app) as manager:
        app.state.llm = llm
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_explain_move_with_templates(
    client: AsyncClient, review: tuple[uuid.UUID, dict[str, int]]
) -> None:
    _, moves = review

    response = await client.post(f"/api/v1/moves/{moves['Nf6']}/explain", json={"lang": "en"})
    default_lang = await client.post(f"/api/v1/moves/{moves['Nf6']}/explain")
    book = await client.post(f"/api/v1/moves/{moves['e4']}/explain", json={"lang": "ru"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["move_id"] == moves["Nf6"]
    assert body["ply"] == 12
    assert body["provider"] == "template"
    assert body["cached"] is False
    assert body["text"].startswith("Mistake: 6... Nf6")
    # Без lang — язык пользователя (ru по умолчанию).
    assert default_lang.json()["text"].startswith("Ошибка: 6... Nf6")
    assert book.json()["text"] == "Ход из дебютной теории."


async def test_explain_move_uses_user_language(
    client: AsyncClient, db: Database, settings: Settings, review: tuple[uuid.UUID, dict[str, int]]
) -> None:
    _, moves = review
    async with db.sessionmaker() as session:
        await session.execute(
            update(User).where(User.id == settings.default_user_id).values(lang="en")
        )
        await session.commit()

    response = await client.post(f"/api/v1/moves/{moves['Nf6']}/explain")

    assert response.json()["text"].startswith("Mistake:")


async def test_explain_move_with_llm_and_fallback(
    settings: Settings, review: tuple[uuid.UUID, dict[str, int]]
) -> None:
    _, moves = review
    llm = FakeLLM("Nf6 пропускает Qb3; лучше было Qf6.", "Qh5!", "Qh5!!")

    async with llm_client(settings, llm) as client:
        good = await client.post(f"/api/v1/moves/{moves['Nf6']}/explain")
        cached = await client.post(f"/api/v1/moves/{moves['Nf6']}/explain")
        hallucinated = await client.post(f"/api/v1/moves/{moves['Qe7']}/explain")

    assert good.json()["provider"] == "fake"
    assert good.json()["text"] == "Nf6 пропускает Qb3; лучше было Qf6."
    assert cached.json()["cached"] is True
    assert hallucinated.json()["provider"] == "template"
    assert hallucinated.json()["text"].startswith("Неточность: 7... Qe7")


async def test_explain_move_not_found(
    client: AsyncClient, db: Database, review: tuple[uuid.UUID, dict[str, int]]
) -> None:
    # Ход чужой партии — 404, как и несуществующий.
    async with db.sessionmaker() as session:
        stranger = User(email=f"{uuid.uuid4().hex}@test")
        session.add(stranger)
        await session.commit()
        stranger_id = stranger.id
    try:
        _, foreign = await insert_review(db, stranger_id)
        response = await client.post(f"/api/v1/moves/{foreign['Nf6']}/explain")
        missing = await client.post("/api/v1/moves/999999999/explain")
        bad_lang = await client.post(
            f"/api/v1/moves/{review[1]['Nf6']}/explain", json={"lang": "de"}
        )
    finally:
        async with db.sessionmaker() as session:
            await session.execute(delete(User).where(User.id == stranger_id))
            await session.commit()

    assert response.status_code == 404
    assert missing.status_code == 404
    assert bad_lang.status_code == 422


async def test_explain_whole_analysis(
    client: AsyncClient, review: tuple[uuid.UUID, dict[str, int]]
) -> None:
    analysis_id, _ = review

    response = await client.post(
        f"/api/v1/analyses/{analysis_id}/explanations", json={"lang": "ru"}
    )

    assert response.status_code == 200, response.text
    items = response.json()
    explained = {
        row["ply"]
        for row in REVIEW["moves"]
        if row["move_class"] in ("inaccuracy", "mistake", "blunder", "brilliant", "great")
        or row["is_miss"]
    }
    assert [item["ply"] for item in items] == sorted(explained)
    assert all(item["provider"] == "template" and item["text"] for item in items)


async def test_summary(client: AsyncClient, review: tuple[uuid.UUID, dict[str, int]]) -> None:
    analysis_id, _ = review

    ru = await client.get(f"/api/v1/analyses/{analysis_id}/summary")
    en = await client.get(f"/api/v1/analyses/{analysis_id}/summary", params={"lang": "en"})

    assert ru.status_code == 200, ru.text
    body = ru.json()
    assert body["analysis_id"] == str(analysis_id)
    assert body["provider"] == "template"
    lines = body["text"].splitlines()
    assert 3 <= len(lines) <= 5
    assert lines[0].startswith("- Точность: Paul Morphy (белые)")
    assert en.json()["text"].startswith("- Accuracy: Paul Morphy (White)")


async def test_summary_and_batch_need_finished_analysis(
    client: AsyncClient, db: Database, settings: Settings, review: tuple[uuid.UUID, dict[str, int]]
) -> None:
    running, _ = await insert_review(db, settings.default_user_id, AnalysisStatus.RUNNING)

    summary = await client.get(f"/api/v1/analyses/{running}/summary")
    batch = await client.post(f"/api/v1/analyses/{running}/explanations")
    missing = await client.get(f"/api/v1/analyses/{uuid.uuid4()}/summary")

    assert summary.status_code == 409
    assert batch.status_code == 409
    assert missing.status_code == 404


async def test_summary_uses_shown_accuracy(
    client: AsyncClient, db: Database, review: tuple[uuid.UUID, dict[str, int]]
) -> None:
    # Как на плашках: официальная точность Chess.com, иначе наша «как у Chess.com».
    analysis_id, _ = review
    async with db.sessionmaker() as session:
        analysis = await session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.cc_black_accuracy = 55.55
        game = await session.get(Game, analysis.game_id)
        assert game is not None
        game.source_white_accuracy = 77.23
        await session.commit()

    response = await client.get(f"/api/v1/analyses/{analysis_id}/summary")

    first = response.json()["text"].splitlines()[0]
    assert "(белые) — 77.2%" in first
    assert "(чёрные) — 55.5%" in first or "(чёрные) — 55.6%" in first
