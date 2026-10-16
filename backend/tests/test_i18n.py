"""i18n на backend: язык объяснений и итога партии — из профиля (`users.lang`), ошибки —
с машинным кодом и параметрами (тексты переводит интерфейс)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import Settings
from app.db.models import User
from app.db.session import Database
from tests.test_api_explain import insert_review

pytestmark = pytest.mark.integration


@pytest.fixture
async def russian_afterwards(db: Database, settings: Settings) -> AsyncIterator[None]:
    yield
    async with db.sessionmaker() as session:
        await session.execute(
            update(User).where(User.id == settings.default_user_id).values(lang="ru")
        )
        await session.commit()


@pytest.mark.usefixtures("russian_afterwards")
async def test_profile_language_drives_explanations_and_summary(
    client: AsyncClient, db: Database, settings: Settings
) -> None:
    analysis_id, moves = await insert_review(db, settings.default_user_id)
    explain = f"/api/v1/moves/{moves['Nf6']}/explain"
    summary = f"/api/v1/analyses/{analysis_id}/summary"

    ru_move = (await client.post(explain)).json()["text"]
    ru_summary = (await client.get(summary)).json()["text"]
    profile = await client.patch("/api/v1/auth/me", json={"lang": "en"})
    en_move = (await client.post(explain)).json()["text"]
    en_summary = (await client.get(summary)).json()["text"]
    # Явный язык запроса важнее профиля.
    forced = (await client.post(explain, json={"lang": "ru"})).json()["text"]

    assert profile.json()["lang"] == "en"
    assert ru_move.startswith("Ошибка: 6... Nf6")
    assert en_move.startswith("Mistake: 6... Nf6")
    assert "точность" in ru_summary.lower()
    assert "accuracy" in en_summary.lower()
    assert forced == ru_move


@pytest.mark.parametrize(
    ("pgn", "code", "params"),
    [
        ("1. e4 e5 2. Ke3 *", "pgn_invalid", {"game": 1}),
        ("просто текст", "pgn_no_moves", {"game": 1}),
        ('[Variant "Atomic"]\n\n1. e4 *', "pgn_variant", {"game": 1}),
    ],
)
async def test_pgn_errors_have_codes(
    client: AsyncClient, db: Database, pgn: str, code: str, params: dict[str, object]
) -> None:
    response = await client.post("/api/v1/games/pgn", json={"pgn": pgn})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == code
    assert params.items() <= body["params"].items()
    assert isinstance(body["detail"], str)


async def test_not_found_and_validation_codes(client: AsyncClient, db: Database) -> None:
    missing = await client.get(f"/api/v1/games/{uuid.uuid4()}")
    invalid = await client.post("/api/v1/imports/lichess", json={"username": "no spaces!"})
    no_route = await client.get("/api/v1/nope")

    assert missing.json() == {
        "detail": "Партия не найдена",
        "code": "game_not_found",
        "params": {},
    }
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_error"
    assert isinstance(invalid.json()["detail"], list)
    assert no_route.status_code == 404
    assert no_route.json()["code"] == "http_error"
