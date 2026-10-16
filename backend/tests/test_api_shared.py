"""Публичные ссылки на разбор: `/shared/{token}` без входа, «Поделиться» владельцем."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, select

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Explanation, Game
from app.db.session import Database
from tests.conftest import api_client
from tests.test_api_explain import insert_review
from tests.test_explain_service import FakeLLM
from tests.test_ratelimit import assert_limited, limited

pytestmark = pytest.mark.integration


@pytest.fixture
async def anonymous(settings: Settings, migrated_db: str) -> AsyncIterator[AsyncClient]:
    async with api_client(settings, anonymous=True) as client:
        yield client


@pytest.fixture
async def shared(
    client: AsyncClient, db: Database, settings: Settings
) -> tuple[str, uuid.UUID, dict[str, int]]:
    """Разобранная партия dev-пользователя с публичной ссылкой: (токен, id анализа, ходы)."""
    async with db.sessionmaker() as session:
        await session.execute(delete(Explanation))
        await session.commit()
    analysis_id, moves = await insert_review(db, settings.default_user_id)
    async with db.sessionmaker() as session:
        game_id = await session.scalar(select(Game.id))
    response = await client.post(f"/api/v1/games/{game_id}/share")
    assert response.status_code == 200, response.text
    token: str = response.json()["token"]
    return token, analysis_id, moves


async def test_share_is_idempotent_and_revocable(
    client: AsyncClient, anonymous: AsyncClient, db: Database, settings: Settings
) -> None:
    await insert_review(db, settings.default_user_id)
    async with db.sessionmaker() as session:
        game_id = await session.scalar(select(Game.id))

    first = await client.post(f"/api/v1/games/{game_id}/share")
    again = await client.post(f"/api/v1/games/{game_id}/share")
    current = await client.get(f"/api/v1/games/{game_id}/share")
    token = first.json()["token"]

    assert first.status_code == again.status_code == current.status_code == 200
    assert again.json() == current.json() == first.json()
    assert first.json()["url"] == f"http://localhost:3000/share/{token}"
    assert len(token) >= 22
    assert (await anonymous.get(f"/api/v1/shared/{token}")).status_code == 200

    revoked = await client.delete(f"/api/v1/games/{game_id}/share")
    assert revoked.status_code == 204
    gone = await anonymous.get(f"/api/v1/shared/{token}")
    assert gone.status_code == 404
    assert gone.json()["code"] == "share_not_found"
    not_shared = await client.get(f"/api/v1/games/{game_id}/share")
    assert not_shared.status_code == 404
    assert not_shared.json()["code"] == "share_not_found"
    # Повторная публикация — новая ссылка, старая не оживает.
    renewed = await client.post(f"/api/v1/games/{game_id}/share")
    assert renewed.json()["token"] != token
    # Без входа управлять ссылками нельзя.
    assert (await anonymous.post(f"/api/v1/games/{game_id}/share")).status_code == 401
    assert (await anonymous.delete(f"/api/v1/games/{game_id}/share")).status_code == 401


async def test_shared_game_is_public(
    anonymous: AsyncClient, client: AsyncClient, shared: tuple[str, uuid.UUID, dict[str, int]]
) -> None:
    token, analysis_id, _ = shared

    response = await anonymous.get(f"/api/v1/shared/{token}")

    assert response.status_code == 200, response.text
    body = response.json()
    game_id = body["id"]
    owner_view = (await client.get(f"/api/v1/games/{game_id}")).json()
    # Тот же ответ, что у владельца в `GET /games/{id}`.
    assert body == owner_view
    assert body["analysis"]["id"] == str(analysis_id)
    assert body["analysis"]["status"] == "done"
    assert len(body["analysis"]["moves"]) > 0
    assert "share_token" not in body
    assert "user_id" not in body


async def test_unknown_token_is_not_found(anonymous: AsyncClient, db: Database) -> None:
    for url in (
        "/api/v1/shared/nope",
        "/api/v1/shared/nope/summary",
        f"/api/v1/shared/{'x' * 65}",
    ):
        response = await anonymous.get(url)
        assert response.status_code in (404, 422), url
    missing = await anonymous.get("/api/v1/shared/nope")
    assert missing.json()["code"] == "share_not_found"
    explain = await anonymous.post("/api/v1/shared/nope/moves/1/explain", json={})
    assert explain.json()["code"] == "share_not_found"


async def test_explain_and_summary_by_token(
    anonymous: AsyncClient, shared: tuple[str, uuid.UUID, dict[str, int]]
) -> None:
    token, analysis_id, moves = shared

    explained = await anonymous.post(
        f"/api/v1/shared/{token}/moves/{moves['Nf6']}/explain", json={"lang": "en"}
    )
    default_lang = await anonymous.post(f"/api/v1/shared/{token}/moves/{moves['Nf6']}/explain")
    summary = await anonymous.get(f"/api/v1/shared/{token}/summary", params={"lang": "en"})
    summary_ru = await anonymous.get(f"/api/v1/shared/{token}/summary")

    assert explained.status_code == 200, explained.text
    assert explained.json()["text"].startswith("Mistake: 6... Nf6")
    assert explained.json()["ply"] == 12
    assert default_lang.json()["text"].startswith("Ошибка: 6... Nf6")
    assert summary.status_code == 200
    assert summary.json()["analysis_id"] == str(analysis_id)
    assert summary.json()["text"].startswith("- Accuracy:")
    assert summary_ru.json()["text"].startswith("- Точность:")


async def test_moves_outside_latest_analysis_are_not_found(
    anonymous: AsyncClient,
    db: Database,
    settings: Settings,
    shared: tuple[str, uuid.UUID, dict[str, int]],
) -> None:
    token, _, moves = shared
    # Ход другой партии того же владельца (без ссылки) и несуществующий ход.
    _, other = await insert_review(db, settings.default_user_id)
    foreign = await anonymous.post(f"/api/v1/shared/{token}/moves/{other['Nf6']}/explain")
    missing = await anonymous.post(f"/api/v1/shared/{token}/moves/999999999/explain")
    # Новый анализ той же партии: ходы прежнего по ссылке больше не объясняются.
    async with db.sessionmaker() as session:
        game = await session.scalar(select(Game).where(Game.share_token == token))
        assert game is not None
        session.add(Analysis(game_id=game.id, depth=20, status=AnalysisStatus.QUEUED))
        await session.commit()
    stale = await anonymous.post(f"/api/v1/shared/{token}/moves/{moves['Nf6']}/explain")

    for response in (foreign, missing, stale):
        assert response.status_code == 404
        assert response.json()["code"] == "move_not_found"


async def test_shared_summary_of_unfinished_analysis(
    client: AsyncClient, anonymous: AsyncClient, db: Database, settings: Settings
) -> None:
    await insert_review(db, settings.default_user_id, AnalysisStatus.RUNNING)
    async with db.sessionmaker() as session:
        game_id = await session.scalar(select(Game.id))
    token = (await client.post(f"/api/v1/games/{game_id}/share")).json()["token"]

    detail = await anonymous.get(f"/api/v1/shared/{token}")
    summary = await anonymous.get(f"/api/v1/shared/{token}/summary")

    assert detail.json()["analysis"]["status"] == "running"
    assert detail.json()["analysis"]["moves"] == []
    assert summary.status_code == 409
    assert summary.json()["code"] == "analysis_not_ready"


async def test_shared_game_without_analysis(
    client: AsyncClient, anonymous: AsyncClient, db: Database
) -> None:
    pgn = (
        '[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n'
    )
    (game,) = (await client.post("/api/v1/games/pgn", json={"pgn": pgn})).json()
    token = (await client.post(f"/api/v1/games/{game['id']}/share")).json()["token"]

    detail = await anonymous.get(f"/api/v1/shared/{token}")
    summary = await anonymous.get(f"/api/v1/shared/{token}/summary")
    explain = await anonymous.post(f"/api/v1/shared/{token}/moves/1/explain")

    assert detail.status_code == 200
    assert detail.json()["analysis"] is None
    assert summary.status_code == 404
    assert summary.json()["code"] == "analysis_not_found"
    assert explain.json()["code"] == "move_not_found"


async def test_shared_llm_is_limited_by_ip(
    redis: Redis, settings: Settings, shared: tuple[str, uuid.UUID, dict[str, int]]
) -> None:
    token, _, moves = shared
    rules = limited(settings, llm="2/hour")
    explain = f"/api/v1/shared/{token}/moves/{moves['Nf6']}/explain"

    # Шаблоны — без лимита.
    async with api_client(rules, anonymous=True) as templates:
        responses = [await templates.post(explain, json={"lang": "en"}) for _ in range(4)]
    assert {response.status_code for response in responses} == {200}

    def with_llm(app: FastAPI) -> None:
        app.state.llm = FakeLLM()

    async with api_client(rules, anonymous=True, setup=with_llm) as client:
        first = await client.post(explain)
        summary = await client.get(f"/api/v1/shared/{token}/summary")
        third = await client.post(explain)

    assert first.status_code == summary.status_code == 200
    assert_limited(third, "llm")
