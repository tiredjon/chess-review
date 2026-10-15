"""API партий: импорт PGN, список с курсором, карточка партии."""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import Settings
from app.db.models import User
from app.db.session import Database

pytestmark = pytest.mark.integration

DATA = Path(__file__).parent / "data"
OPERA = (DATA / "opera_game.pgn").read_text(encoding="utf-8")


def dated_game(white: str, date: str | None) -> str:
    tags = f'[White "{white}"]\n[Black "Opponent"]\n[Result "1-0"]\n'
    if date is not None:
        tags += f'[UTCDate "{date}"]\n[UTCTime "12:00:00"]\n'
    return f"{tags}\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n"


async def import_pgn(client: AsyncClient, pgn: str) -> list[dict[str, object]]:
    response = await client.post("/api/v1/games/pgn", json={"pgn": pgn})
    assert response.status_code == 200, response.text
    games: list[dict[str, object]] = response.json()
    return games


async def test_import_pgn_is_idempotent(client: AsyncClient, db: Database) -> None:
    (game,) = await import_pgn(client, OPERA)

    assert game["source"] == "pgn"
    assert game["white"] == "Paul Morphy"
    assert game["result"] == "1-0"
    assert game["opening_eco"] == "C41"
    assert game["opening_name"] == "Philidor Defense"
    assert game["analysis"] is None
    assert game["user_color"] is None

    # Та же партия с другим форматированием — та же запись.
    reformatted = OPERA.replace("1. e4", "1.e4 {начало}").replace(" 2. ", "\n2.  ")
    again = await import_pgn(client, reformatted)
    assert [g["id"] for g in again] == [game["id"]]


async def test_import_several_games_dedups_inside_text(client: AsyncClient, db: Database) -> None:
    pgn = "\n\n".join([dated_game("A", "2024.01.01"), OPERA, dated_game("A", "2024.01.01")])

    games = await import_pgn(client, pgn)

    assert [g["white"] for g in games] == ["A", "Paul Morphy"]


async def test_import_detects_user_color(
    client: AsyncClient, db: Database, settings: Settings
) -> None:
    async with db.sessionmaker() as session:
        await session.execute(
            update(User).where(User.id == settings.default_user_id).values(lichess_username="alice")
        )
        await session.commit()
    try:
        (game,) = await import_pgn(client, dated_game("Alice", "2024.05.05"))
    finally:
        async with db.sessionmaker() as session:
            await session.execute(
                update(User)
                .where(User.id == settings.default_user_id)
                .values(lichess_username=None)
            )
            await session.commit()

    assert game["user_color"] == "white"


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({"pgn": "1. e4 e5 2. Ke3 *"}, "Партия 1: illegal san"),
        ({"pgn": "просто текст"}, "в партии нет ходов"),
    ],
)
async def test_import_rejects_bad_pgn(
    client: AsyncClient, db: Database, payload: dict[str, str], detail: str
) -> None:
    response = await client.post("/api/v1/games/pgn", json=payload)

    assert response.status_code == 422
    assert detail in response.json()["detail"]


async def test_import_validates_body(client: AsyncClient, db: Database) -> None:
    response = await client.post("/api/v1/games/pgn", json={"pgn": ""})

    assert response.status_code == 422


async def test_list_games_paginates_newest_first(client: AsyncClient, db: Database) -> None:
    pgn = "\n\n".join(
        [
            dated_game("Old", "2023.01.01"),
            dated_game("NoDate1", None),
            dated_game("New", "2024.06.01"),
            dated_game("Mid", "2024.01.01"),
            dated_game("NoDate2", None),
        ]
    )
    await import_pgn(client, pgn)

    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params: dict[str, str | int] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        response = await client.get("/api/v1/games", params=params)
        assert response.status_code == 200
        page = response.json()
        seen += [item["white"] for item in page["items"]]
        pages += 1
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert pages == 3
    assert seen[:3] == ["New", "Mid", "Old"]
    # Партии без даты — в конце, в каком-то стабильном порядке.
    assert sorted(seen[3:]) == ["NoDate1", "NoDate2"]


async def test_list_games_filters_and_validates(client: AsyncClient, db: Database) -> None:
    await import_pgn(client, OPERA)

    pgn_games = await client.get("/api/v1/games", params={"source": "pgn"})
    lichess_games = await client.get("/api/v1/games", params={"source": "lichess"})
    bad_cursor = await client.get("/api/v1/games", params={"cursor": "не-курсор"})
    bad_limit = await client.get("/api/v1/games", params={"limit": 0})

    assert len(pgn_games.json()["items"]) == 1
    assert pgn_games.json()["next_cursor"] is None
    assert lichess_games.json()["items"] == []
    assert bad_cursor.status_code == 422
    assert bad_limit.status_code == 422


async def test_get_game(client: AsyncClient, db: Database) -> None:
    (game,) = await import_pgn(client, OPERA)

    response = await client.get(f"/api/v1/games/{game['id']}")
    missing = await client.get(f"/api/v1/games/{uuid.uuid4()}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == game["id"]
    assert "17. Rd8#" in detail["pgn"]
    assert detail["analysis"] is None
    assert missing.status_code == 404
