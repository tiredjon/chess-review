"""API идей позиции: `GET /api/v1/plans?fen=&lang=`."""

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import Settings
from app.db.models import User
from app.db.session import Database
from tests.conftest import api_client
from tests.plans_lines import board_of

pytestmark = pytest.mark.integration

URL = "/api/v1/plans"


async def test_plans_ru(client: AsyncClient) -> None:
    fen = board_of("tarrasch_iqp").fen()
    response = await client.get(URL, params={"fen": fen})
    assert response.status_code == 200
    body = response.json()
    assert body["ideas"]["structures"] == ["isolani"]
    assert body["rendered"]["structures"] == ["isolani"]
    assert body["rendered"]["structure_title"] == "Изолированная пешка d5"
    keys = [(i["side"], i["key"]) for i in body["ideas"]["ideas"]]
    assert ("black", "isolani.activity") in keys
    assert [(i["side"], i["key"]) for i in body["rendered"]["ideas"]] == keys
    assert body["ideas"]["weaknesses"]
    assert {"side", "uci", "san", "target", "legal_now"} <= set(body["ideas"]["breaks"][0])


async def test_plans_en(client: AsyncClient) -> None:
    fen = board_of("najdorf_be2_e5").fen()
    response = await client.get(URL, params={"fen": fen, "lang": "en"})
    assert response.status_code == 200
    rendered = response.json()["rendered"]
    assert rendered["structures"] == ["sicilian_d6_e5"]
    assert rendered["structure_title"]
    assert "d5" in rendered["structure_summary"]
    assert all(not any("а" <= ch <= "я" for ch in i["text"]) for i in rendered["ideas"])


async def test_plans_default_lang_from_user(
    settings: Settings, db: Database, client: AsyncClient
) -> None:
    fen = board_of("tarrasch_iqp").fen()
    user_id = settings.default_user_id
    async with db.sessionmaker() as session:
        await session.execute(update(User).where(User.id == user_id).values(lang="en"))
        await session.commit()
    try:
        english = await client.get(URL, params={"fen": fen})
        forced = await client.get(URL, params={"fen": fen, "lang": "ru"})
    finally:
        async with db.sessionmaker() as session:
            await session.execute(update(User).where(User.id == user_id).values(lang="ru"))
            await session.commit()
    assert english.status_code == forced.status_code == 200
    assert english.json()["rendered"]["structure_title"] == "Isolated pawn on d5"
    assert forced.json()["rendered"]["structure_title"] == "Изолированная пешка d5"


async def test_plans_start_position(client: AsyncClient) -> None:
    response = await client.get(URL, params={"fen": board_of("start").fen()})
    assert response.status_code == 200
    rendered = response.json()["rendered"]
    assert rendered["structures"] == []
    assert rendered["structure_title"] is None


@pytest.mark.parametrize("fen", ["nonsense", "8/8/8/8/8/8/8/8 w - - 0 1"])
async def test_plans_invalid_fen(client: AsyncClient, fen: str) -> None:
    response = await client.get(URL, params={"fen": fen})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_fen"


async def test_plans_bad_lang(client: AsyncClient) -> None:
    response = await client.get(URL, params={"fen": board_of("start").fen(), "lang": "de"})
    assert response.status_code == 422


async def test_plans_requires_auth(settings: Settings, migrated_db: str) -> None:
    async with api_client(settings, anonymous=True) as anon:
        response = await anon.get(URL, params={"fen": board_of("start").fen()})
    assert response.status_code == 401
