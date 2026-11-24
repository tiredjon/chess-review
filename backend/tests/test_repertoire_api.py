"""Репертуар: сервис и API на партиях в БД (оба цвета, пустой репертуар, изоляция)."""

import time
import uuid
from datetime import UTC, datetime
from typing import Any

import chess
import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.config import Settings
from app.db.models import Color, Game, GameSource, User
from app.db.session import Database
from app.repertoire.service import clear_cache, parse_moves
from tests.conftest import api_client

pytestmark = pytest.mark.integration


def pgn(san: str, result: str, *, fen: str | None = None) -> str:
    """PGN с комментариями (%clk) и вариантом — как в хранимых партиях."""
    board = chess.Board()
    out = []
    for i, token in enumerate(san.split()):
        number = f"{i // 2 + 1}. " if i % 2 == 0 else ""
        out.append(f"{number}{token} {{ [%clk 0:03:00] }}")
        board.push(board.parse_san(token))
    extra = f'[SetUp "1"]\n[FEN "{fen}"]\n' if fen else ""
    head = f'[Event "t"]\n[White "w"]\n[Black "b"]\n[Result "{result}"]\n{extra}'
    return f"{head}\n{' '.join(out)} {result}\n"


_counter = iter(range(10_000))


def game(
    user_id: uuid.UUID,
    san: str,
    color: Color | None,
    result: str,
    *,
    day: int = 1,
    name: str | None = None,
    eco: str | None = None,
    text: str | None = None,
) -> Game:
    return Game(
        user_id=user_id,
        source=GameSource.PGN,
        external_id=f"g{next(_counter)}",
        pgn=text or pgn(san, result),
        white="me",
        black="op",
        result=result,
        played_at=datetime(2026, 1, day, tzinfo=UTC),
        user_color=color,
        opening_name=name,
        opening_eco=eco,
    )


@pytest.fixture(autouse=True)
async def clean(db: Database, settings: Settings) -> None:
    clear_cache()
    async with db.sessionmaker() as session:
        await session.execute(delete(Game).where(Game.user_id == settings.default_user_id))
        await session.commit()


async def add(db: Database, games: list[Game]) -> None:
    async with db.sessionmaker() as session:
        session.add_all(games)
        await session.commit()


async def fetch(client: AsyncClient, path: str, **params: Any) -> Any:
    response = await client.get(f"/api/v1/repertoire/{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_parse_moves_ignores_comments_and_unsupported() -> None:
    moves = parse_moves(pgn("e4 e5 Nf3", "1-0"))
    assert moves is not None
    assert [m.uci() for m in moves] == ["e2e4", "e7e5", "g1f3"]
    start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    assert parse_moves(pgn("e4", "1-0", fen=start)) is None
    assert parse_moves("") is None


async def test_tree_filters_color_and_ignores_games_without_color(
    client: AsyncClient, db: Database, settings: Settings
) -> None:
    uid = settings.default_user_id
    await add(
        db,
        [
            game(uid, "e4 e5 Nf3", Color.WHITE, "1-0", day=1),
            game(uid, "e4 e5 Bc4", Color.WHITE, "0-1", day=2),
            game(uid, "d4 d5", Color.WHITE, "*", day=3),  # не окончена
            game(uid, "e4 c5 Nf3", Color.BLACK, "1-0", day=4),
            game(uid, "e4 c5 Nf3", Color.BLACK, "0-1", day=5),
            game(uid, "e4 e5", None, "1-0", day=6),  # цвет неизвестен
        ],
    )

    white = await fetch(client, "tree", color="white", min_games=1)
    assert white["color"] == "white"
    assert white["total_games"] == 2
    nodes = white["nodes"]
    assert nodes[0]["games"] == 2
    assert nodes[0]["children"] == [1]
    e4 = nodes[1]
    assert (e4["san"], e4["uci"], e4["mover"], e4["parent"]) == ("e4", "e2e4", "learner", 0)
    assert (e4["wins"], e4["draws"], e4["losses"]) == (1, 0, 1)
    assert e4["last_played_at"].startswith("2026-01-02")
    assert e4["book"] is True
    assert set(nodes[0]) == {
        "id", "parent", "children", "ply", "uci", "san", "mover", "fen",
        "book", "name", "games", "wins", "draws", "losses", "last_played_at",
    }  # fmt: skip

    black = await fetch(client, "tree", color="black", min_games=2)
    assert black["total_games"] == 2
    assert [n["san"] for n in black["nodes"]] == [None, "e4", "c5", "Nf3"]
    assert [n["mover"] for n in black["nodes"]] == [None, "opponent", "learner", "opponent"]
    assert (black["nodes"][2]["wins"], black["nodes"][2]["losses"]) == (1, 1)


async def test_tree_params_and_defaults(
    client: AsyncClient, db: Database, settings: Settings
) -> None:
    uid = settings.default_user_id
    long = "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7"
    await add(
        db, [game(uid, long, Color.WHITE, "1-0", day=1), game(uid, long, Color.WHITE, "1-0", day=2)]
    )

    default = await fetch(client, "tree", color="white")
    assert max(n["ply"] for n in default["nodes"]) == 10
    short = await fetch(client, "tree", color="white", max_ply=4)
    assert max(n["ply"] for n in short["nodes"]) == 4
    assert (await fetch(client, "tree", color="white", min_games=3))["nodes"][0]["children"] == []
    for bad in ({"max_ply": 41}, {"max_ply": 0}, {"min_games": 0}, {"color": "red"}):
        response = await client.get("/api/v1/repertoire/tree", params={"color": "white", **bad})
        assert response.status_code == 422
    assert (await client.get("/api/v1/repertoire/tree")).status_code == 422


async def test_openings_list(client: AsyncClient, db: Database, settings: Settings) -> None:
    uid = settings.default_user_id
    ruy = "e4 e5 Nf3 Nc6 Bb5 a6"
    await add(
        db,
        [
            game(uid, ruy, Color.WHITE, "1-0", day=1, name="Ruy Lopez: Morphy Defense", eco="C78"),
            game(uid, ruy, Color.WHITE, "0-1", day=3, name="Ruy Lopez: Morphy Defense", eco="C78"),
            game(uid, "d4 d5 c4", Color.WHITE, "1/2-1/2", day=2, name="Queen's Gambit", eco="D06"),
            game(uid, "e4 c5", Color.BLACK, "1-0", day=4, name="Sicilian Defense", eco="B20"),
            game(uid, "a3 a6", Color.WHITE, "1-0", day=5),  # без названия
        ],
    )

    white = await fetch(client, "openings", color="white")
    assert [o["name"] for o in white] == ["Ruy Lopez: Morphy Defense", "Queen's Gambit"]
    first = white[0]
    assert first["eco"] == "C78"
    assert (first["games"], first["wins"], first["draws"], first["losses"]) == (2, 1, 0, 1)
    assert first["line_uci"] == ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"]
    assert first["book_exit_ply"] == 6
    assert first["last_played_at"].startswith("2026-01-03")
    assert set(first) == {
        "name", "eco", "games", "wins", "draws", "losses", "line_uci", "book_exit_ply",
        "last_played_at",
    }  # fmt: skip

    black = await fetch(client, "openings", color="black")
    assert [(o["name"], o["wins"], o["losses"]) for o in black] == [("Sicilian Defense", 0, 1)]


async def test_empty_repertoire(client: AsyncClient) -> None:
    assert await fetch(client, "openings", color="white") == []
    tree = await fetch(client, "tree", color="black")
    assert tree == {"color": "black", "total_games": 0, "nodes": []}


async def test_users_are_isolated(client: AsyncClient, db: Database, settings: Settings) -> None:
    owner = settings.default_user_id
    async with db.sessionmaker() as session:
        other = User(email=f"rep-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(other)
        await session.commit()
    await add(
        db,
        [
            game(owner, "e4 e5", Color.WHITE, "1-0", name="King's Pawn Game", eco="C20"),
            game(other.id, "d4 d5", Color.WHITE, "1-0", name="Queen's Pawn Game", eco="D00"),
            game(other.id, "d4 d5", Color.WHITE, "1-0", name="Queen's Pawn Game", eco="D00"),
        ],
    )

    mine = await fetch(client, "tree", color="white", min_games=1)
    assert mine["total_games"] == 1
    assert [n["san"] for n in mine["nodes"]] == [None, "e4", "e5"]
    async with api_client(settings, other.id) as theirs:
        data = await fetch(theirs, "tree", color="white", min_games=1)
        assert data["total_games"] == 2
        assert [n["san"] for n in data["nodes"]] == [None, "d4", "d5"]
        names = [o["name"] for o in await fetch(theirs, "openings", color="white")]
        assert names == ["Queen's Pawn Game"]
    assert [o["name"] for o in await fetch(client, "openings", color="white")] == [
        "King's Pawn Game"
    ]


async def test_requires_auth(settings: Settings) -> None:
    async with api_client(settings, anonymous=True) as anonymous:
        response = await anonymous.get("/api/v1/repertoire/tree", params={"color": "white"})
        assert response.status_code == 401


async def test_cache_invalidated_when_games_change(
    client: AsyncClient, db: Database, settings: Settings
) -> None:
    uid = settings.default_user_id
    await add(db, [game(uid, "e4 e5", Color.WHITE, "1-0")])
    assert (await fetch(client, "tree", color="white", min_games=1))["total_games"] == 1
    await add(db, [game(uid, "d4 d5", Color.WHITE, "1-0")])
    assert (await fetch(client, "tree", color="white", min_games=1))["total_games"] == 2


async def test_warm_response_on_user_scale(
    client: AsyncClient, db: Database, settings: Settings
) -> None:
    """~560 партий на цвет по ~60 ходов: тёплый ответ укладывается в 500 мс."""
    uid = settings.default_user_id
    lines = [
        "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3 Nb8 d4 Nbd7",
        "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be3 e5 Nb3 Be6 f3 Be7 Qd2 O-O O-O-O Nbd7",
        "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6 Bh4 b6 cxd5 Nxd5 Bxe7 Qxe7 Nxd5 exd5",
        "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7 Ne1 Nd7 Be3 f5",
    ]
    games = [
        game(
            uid,
            " ".join(lines[i % 4].split()[: 12 + i % 9]),
            Color.WHITE,
            ("1-0", "0-1", "1/2-1/2")[i % 3],
            day=1 + i % 28,
            name=f"Opening {i % 20}",
        )
        for i in range(560)
    ]
    await add(db, games)

    started = time.perf_counter()
    await fetch(client, "tree", color="white")
    cold = time.perf_counter() - started
    started = time.perf_counter()
    await fetch(client, "tree", color="white", max_ply=30)
    await fetch(client, "openings", color="white")
    warm = (time.perf_counter() - started) / 2
    print(f"репертуар: холодный {cold:.2f} с, тёплый {warm * 1000:.0f} мс")
    assert warm < 0.5
