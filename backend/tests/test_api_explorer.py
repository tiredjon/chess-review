"""API Explorer: позиция, партия мастеров, ошибки и вход."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import Settings
from tests.conftest import api_client
from tests.explorer_fakes import FakeExplorer

START = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


@asynccontextmanager
async def client_with(
    settings: Settings, fake: FakeExplorer, *, anonymous: bool = False
) -> AsyncIterator[AsyncClient]:
    def setup(app: FastAPI) -> None:
        app.state.explorer = fake

    async with api_client(settings, setup=setup, anonymous=anonymous) as ac:
        yield ac


@pytest.fixture(autouse=True)
def _db(migrated_db: str) -> None:
    """Миграции нужны для входа (пользователь из миграции)."""


async def test_position(settings: Settings) -> None:
    fake = FakeExplorer()
    async with client_with(settings, fake) as ac:
        response = await ac.get("/api/v1/explorer", params={"fen": START})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "masters"
    assert body["games"] == body["white"] + body["draws"] + body["black"]
    assert body["moves"][0]["san"] == "c5"
    assert body["moves"][0]["games"] == 194269 + 273851 + 159166
    assert body["top_games"][0]["id"] == "zEaZZlau"
    assert body["opening_name"] == "King's Pawn Game"


async def test_source_lichess(settings: Settings) -> None:
    async with client_with(settings, FakeExplorer()) as ac:
        response = await ac.get("/api/v1/explorer", params={"fen": START, "source": "lichess"})

    assert response.status_code == 200
    assert response.json()["source"] == "lichess"
    assert response.json()["top_games"] == []


@pytest.mark.parametrize(
    "fen", ["not a fen", "8/8/8/8/8/8/8/8 w - - 0 1"], ids=["syntax", "impossible"]
)
async def test_invalid_fen(settings: Settings, fen: str) -> None:
    fake = FakeExplorer()
    async with client_with(settings, fake) as ac:
        response = await ac.get("/api/v1/explorer", params={"fen": fen})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_fen"
    assert fake.position_calls == []


async def test_unknown_source(settings: Settings) -> None:
    async with client_with(settings, FakeExplorer()) as ac:
        response = await ac.get("/api/v1/explorer", params={"fen": START, "source": "x"})

    assert response.status_code == 422


async def test_unavailable_is_503(settings: Settings) -> None:
    async with client_with(settings, FakeExplorer(fail=True)) as ac:
        response = await ac.get("/api/v1/explorer", params={"fen": START})
        game = await ac.get("/api/v1/explorer/games/zEaZZlau")

    for r in (response, game):
        assert r.status_code == 503
        assert r.json()["code"] == "explorer_unavailable"


async def test_game(settings: Settings) -> None:
    async with client_with(settings, FakeExplorer()) as ac:
        response = await ac.get("/api/v1/explorer/games/zEaZZlau")

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["white"], body["black"]) == ("zEaZZlau", "Nakamura, Hi", "Carlsen, M.")
    assert (body["white_rating"], body["year"], body["result"]) == (2816, 2025, "0-1")
    assert "1. e4 d6" in body["pgn"]


async def test_game_bad_id(settings: Settings) -> None:
    fake = FakeExplorer()
    async with client_with(settings, fake) as ac:
        response = await ac.get("/api/v1/explorer/games/..%2Fetc")

    assert response.status_code in (404, 422)
    assert fake.game_calls == []


async def test_requires_login(settings: Settings) -> None:
    async with client_with(settings, FakeExplorer(), anonymous=True) as ac:
        assert (await ac.get("/api/v1/explorer", params={"fen": START})).status_code == 401
        assert (await ac.get("/api/v1/explorer/games/zEaZZlau")).status_code == 401
