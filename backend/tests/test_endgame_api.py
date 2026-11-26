"""API тренажёра эндшпиля: каталог с прогрессом, позиции из своих партий (правила отбора),
таблицы (фейк), попытки, лимит, изоляция пользователей."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete

from app.core.config import Settings
from app.core.rates import Rate
from app.db.models import (
    Analysis,
    AnalysisStatus,
    Color,
    EndgameAttempt,
    Game,
    GameSource,
    Move,
    User,
)
from app.db.session import Database
from app.endgames.catalog import CATALOG
from app.review.types import MoveClass, Phase
from tests.conftest import api_client
from tests.endgame_fakes import FakeTablebase

pytestmark = pytest.mark.integration

LUCENA = "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1"
WHITE_TO_MOVE = "8/8/8/4k3/8/8/8/R3K3 w - - 0 41"
BLACK_TO_MOVE = "8/8/8/4k3/8/8/8/R3K3 b - - 0 41"


@pytest.fixture
async def edb(db: Database) -> Database:
    async with db.sessionmaker() as session:
        await session.execute(delete(EndgameAttempt))
        await session.commit()
    return db


@asynccontextmanager
async def client_with(
    settings: Settings,
    fake: FakeTablebase | None = None,
    *,
    user_id: uuid.UUID | None = None,
    anonymous: bool = False,
) -> AsyncIterator[AsyncClient]:
    def setup(app: FastAPI) -> None:
        app.state.tablebase = fake or FakeTablebase()

    async with api_client(settings, user_id, setup=setup, anonymous=anonymous) as ac:
        yield ac


async def other_user(db: Database) -> uuid.UUID:
    async with db.sessionmaker() as session:
        user = User(email=f"eg-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        return user.id


def mv(
    ply: int,
    cls: MoveClass,
    *,
    win: tuple[float, float] = (80.0, 40.0),
    phase: Phase = Phase.ENDGAME,
    miss: bool = False,
) -> Move:
    return Move(
        ply=ply,
        san=f"m{ply}",
        uci="a1a2",
        fen_before=WHITE_TO_MOVE if ply % 2 == 1 else BLACK_TO_MOVE,
        win_before=win[0],
        win_after=win[1],
        accuracy=50.0,
        move_class=cls,
        is_miss=miss,
        best_uci="a1a5",
        best_san="Ra5+",
        phase=phase,
    )


def game(user_id: uuid.UUID, name: str, color: Color | None, day: int) -> Game:
    return Game(
        user_id=user_id,
        source=GameSource.PGN,
        external_id=f"{name}-{uuid.uuid4().hex[:6]}",
        pgn="*",
        white="me" if color == Color.WHITE else name,
        black="me" if color == Color.BLACK else name,
        result="1/2-1/2",
        played_at=datetime(2026, 10, day, tzinfo=UTC),
        user_color=color,
    )


def done(game_id: uuid.UUID, moves: list[Move], *, created: int = 1) -> Analysis:
    return Analysis(
        game_id=game_id,
        depth=10,
        status=AnalysisStatus.DONE,
        moves=moves,
        created_at=datetime(2026, 10, 1, created, tzinfo=UTC),
    )


@pytest.fixture
async def seeded(edb: Database, settings: Settings) -> dict[str, Any]:
    """G1 — белые, две ошибки в эндшпиле (берётся с большей потерей), ошибка соперника;
    G2 — чёрные, miss → цель «ничья», ошибка миттельшпиля; G3 — ошибка при win% 20 (не берётся);
    G4 — новый анализ ещё идёт, берётся последний готовый; G5 — цвет неизвестен; чужая партия."""
    uid = settings.default_user_id
    stranger = await other_user(edb)
    g1 = game(uid, "Alice", Color.WHITE, 10)
    g2 = game(uid, "Bob", Color.BLACK, 12)
    g3 = game(uid, "Carol", Color.WHITE, 11)
    g4 = game(uid, "Dave", Color.WHITE, 9)
    g5 = game(uid, "Eve", None, 13)
    foreign = game(stranger, "Zed", Color.WHITE, 14)
    async with edb.sessionmaker() as session:
        session.add_all([g1, g2, g3, g4, g5, foreign])
        await session.flush()
        g1_small = mv(41, MoveClass.MISTAKE, win=(80, 40))
        g1_big = mv(43, MoveClass.BLUNDER, win=(70, 10))
        g2_miss = mv(40, MoveClass.INACCURACY, win=(50, 38), miss=True)
        g4_old = mv(51, MoveClass.MISTAKE, win=(90, 60))
        foreign_move = mv(41, MoveClass.BLUNDER)
        g1_opponent = mv(42, MoveClass.BLUNDER)
        session.add_all(
            [
                done(
                    g1.id,
                    [g1_small, g1_opponent, g1_big, mv(45, MoveClass.BEST)],
                ),
                done(
                    g2.id,
                    [mv(30, MoveClass.BLUNDER, phase=Phase.MIDDLEGAME), g2_miss],
                ),
                done(g3.id, [mv(41, MoveClass.BLUNDER, win=(20, 5))]),
                done(g4.id, [g4_old], created=1),
                Analysis(
                    game_id=g4.id,
                    depth=10,
                    status=AnalysisStatus.RUNNING,
                    created_at=datetime(2026, 10, 1, 5, tzinfo=UTC),
                ),
                done(g5.id, [mv(41, MoveClass.BLUNDER)]),
                done(foreign.id, [foreign_move]),
            ]
        )
        await session.commit()
    return {
        "stranger": stranger,
        "g1": g1.id,
        "g2": g2.id,
        "g4": g4.id,
        "g1_big": g1_big.id,
        "g1_small": g1_small.id,
        "g1_opponent": g1_opponent.id,
        "g2_miss": g2_miss.id,
        "g4_old": g4_old.id,
        "foreign_move": foreign_move.id,
    }


async def test_catalog_with_progress(settings: Settings, edb: Database) -> None:
    async with client_with(settings) as ac:
        before = (await ac.get("/api/v1/endgames/catalog")).json()
        r1 = await ac.post(
            "/api/v1/endgames/attempts",
            json={
                "source": "catalog",
                "key": "rook_lucena",
                "goal": "win",
                "success": True,
                "plies": 31,
            },
        )
        r2 = await ac.post(
            "/api/v1/endgames/attempts",
            json={
                "source": "catalog",
                "key": "rook_lucena",
                "goal": "win",
                "success": False,
                "plies": 8,
            },
        )
        after = (await ac.get("/api/v1/endgames/catalog")).json()

    assert before["categories"] == ["pawn", "rook", "queen", "mate"]
    assert [p["id"] for p in before["positions"]] == [p.id for p in CATALOG]
    assert all(p["attempts"] == 0 for p in before["positions"])
    assert r1.json() == {"attempts": 1, "successes": 1}
    assert r2.json() == {"attempts": 2, "successes": 1}
    lucena = next(p for p in after["positions"] if p["id"] == "rook_lucena")
    assert lucena == {
        "id": "rook_lucena",
        "category": "rook",
        "fen": LUCENA,
        "goal": "win",
        "difficulty": 2,
        "color": "white",
        "pieces": 5,
        "attempts": 2,
        "successes": 1,
    }
    philidor = next(p for p in after["positions"] if p["id"] == "rook_philidor")
    assert philidor["color"] == "black"
    assert philidor["goal"] == "draw"


async def test_catalog_attempt_errors(settings: Settings, edb: Database) -> None:
    async with client_with(settings) as ac:
        unknown = await ac.post(
            "/api/v1/endgames/attempts",
            json={"source": "catalog", "key": "nope", "goal": "win", "success": True, "plies": 1},
        )
        wrong_goal = await ac.post(
            "/api/v1/endgames/attempts",
            json={
                "source": "catalog",
                "key": "rook_lucena",
                "goal": "draw",
                "success": True,
                "plies": 1,
            },
        )
        bad_source = await ac.post(
            "/api/v1/endgames/attempts",
            json={"source": "x", "key": "rook_lucena", "goal": "win", "success": True, "plies": 1},
        )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "endgame_not_found"
    assert wrong_goal.status_code == 422
    assert bad_source.status_code == 422


async def test_mine_rules(settings: Settings, seeded: dict[str, Any]) -> None:
    async with client_with(settings) as ac:
        body = (await ac.get("/api/v1/endgames/mine")).json()

    positions = body["positions"]
    # Свежие первыми: G2 (12-е), G1 (10-е), G4 (9-е); G3, G5 и чужая партия не берутся.
    assert [p["game_id"] for p in positions] == [
        str(seeded["g2"]),
        str(seeded["g1"]),
        str(seeded["g4"]),
    ]
    g2, g1, g4 = positions
    assert g1["key"] == str(seeded["g1_big"])  # потеря 60 > 40
    assert g1["ply"] == 43
    assert g1["goal"] == "win"
    assert g1["opponent"] == "Alice"
    assert g1["san"] == "m43"
    assert g1["best_san"] == "Ra5+"
    assert g1["win_before"] == 70.0
    assert g1["fen"] == WHITE_TO_MOVE
    assert g1["pieces"] == 3
    assert g1["attempts"] == 0
    assert g2["key"] == str(seeded["g2_miss"])
    assert g2["goal"] == "draw"
    assert g2["fen"] == BLACK_TO_MOVE
    assert g2["opponent"] == "Bob"
    assert g4["key"] == str(seeded["g4_old"])


async def test_mine_limit(settings: Settings, seeded: dict[str, Any]) -> None:
    async with client_with(settings) as ac:
        two = (await ac.get("/api/v1/endgames/mine", params={"limit": 2})).json()
        huge = await ac.get("/api/v1/endgames/mine", params={"limit": 10_000})
        zero = await ac.get("/api/v1/endgames/mine", params={"limit": 0})
    assert [p["game_id"] for p in two["positions"]] == [str(seeded["g2"]), str(seeded["g1"])]
    assert huge.status_code == 200
    assert zero.status_code == 422


async def test_game_attempts_and_isolation(
    settings: Settings, edb: Database, seeded: dict[str, Any]
) -> None:
    def attempt(key: object, success: bool = True) -> dict[str, Any]:
        return {"source": "game", "key": str(key), "goal": "win", "success": success, "plies": 12}

    async with client_with(settings) as ac:
        own = await ac.post("/api/v1/endgames/attempts", json=attempt(seeded["g1_big"]))
        opponent = await ac.post("/api/v1/endgames/attempts", json=attempt(seeded["g1_opponent"]))
        foreign = await ac.post("/api/v1/endgames/attempts", json=attempt(seeded["foreign_move"]))
        junk = await ac.post("/api/v1/endgames/attempts", json=attempt("12abc"))
        huge = await ac.post("/api/v1/endgames/attempts", json=attempt("9" * 40))
        mine = (await ac.get("/api/v1/endgames/mine")).json()["positions"]

    assert own.status_code == 200
    assert own.json() == {"attempts": 1, "successes": 1}
    for response in (opponent, foreign, junk, huge):
        assert response.status_code == 404
        assert response.json()["code"] == "endgame_not_found"
    g1 = next(p for p in mine if p["key"] == str(seeded["g1_big"]))
    assert (g1["attempts"], g1["successes"]) == (1, 1)

    # Чужой пользователь: свои партии и свой прогресс, наш ход — 404.
    async with client_with(settings, user_id=seeded["stranger"]) as other:
        theirs = (await other.get("/api/v1/endgames/mine")).json()["positions"]
        steal = await other.post("/api/v1/endgames/attempts", json=attempt(seeded["g1_big"]))
        await other.post(
            "/api/v1/endgames/attempts",
            json={
                "source": "catalog",
                "key": "mate_rook",
                "goal": "win",
                "success": True,
                "plies": 40,
            },
        )
        their_catalog = (await other.get("/api/v1/endgames/catalog")).json()["positions"]
    assert [p["key"] for p in theirs] == [str(seeded["foreign_move"])]
    assert steal.status_code == 404
    assert next(p for p in their_catalog if p["id"] == "mate_rook")["attempts"] == 1

    async with client_with(settings) as ac:
        catalog = (await ac.get("/api/v1/endgames/catalog")).json()["positions"]
    assert next(p for p in catalog if p["id"] == "mate_rook")["attempts"] == 0


async def test_tablebase(settings: Settings, edb: Database) -> None:
    fake = FakeTablebase()
    async with client_with(settings, fake) as ac:
        response = await ac.get("/api/v1/endgames/tablebase", params={"fen": LUCENA})

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "win"
    assert body["checkmate"] is False
    assert body["moves"][0] == {
        "uci": "c1d1",
        "san": "Rd1+",
        "category": "win",
        "dtz": body["moves"][0]["dtz"],
        "dtm": body["moves"][0]["dtm"],
    }
    assert body["moves"][0]["dtz"] > 0
    categories = [m["category"] for m in body["moves"]]
    assert categories == sorted(categories, key=["win", "draw", "loss"].index)


@pytest.mark.parametrize(
    "fen",
    [
        "not a fen",
        "8/8/8/8/8/8/8/8 w - - 0 1",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "4k3/ppppp3/8/8/8/8/P7/4K3 w - - 0 1",
    ],
    ids=["syntax", "impossible", "start", "eight-pieces"],
)
async def test_tablebase_invalid_fen(settings: Settings, edb: Database, fen: str) -> None:
    fake = FakeTablebase()
    async with client_with(settings, fake) as ac:
        response = await ac.get("/api/v1/endgames/tablebase", params={"fen": fen})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_fen"
    assert fake.calls == []


async def test_tablebase_unavailable(settings: Settings, edb: Database) -> None:
    async with client_with(settings, FakeTablebase(fail=True)) as ac:
        response = await ac.get("/api/v1/endgames/tablebase", params={"fen": LUCENA})
    assert response.status_code == 503
    assert response.json()["code"] == "tablebase_unavailable"


async def test_tablebase_rate_limit(settings: Settings, edb: Database, redis: Redis) -> None:
    limited = settings.model_copy(
        update={"rate_limit_enabled": True, "rate_limit_tablebase": Rate(2, 3600)}
    )
    async with client_with(limited) as ac:
        # Неверный FEN лимит не тратит.
        assert (await ac.get("/api/v1/endgames/tablebase", params={"fen": "x"})).status_code == 422
        for _ in range(2):
            ok = await ac.get("/api/v1/endgames/tablebase", params={"fen": LUCENA})
            assert ok.status_code == 200
        over = await ac.get("/api/v1/endgames/tablebase", params={"fen": LUCENA})
    assert over.status_code == 429
    assert over.json()["params"]["scope"] == "tablebase"
    assert "Retry-After" in over.headers


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/endgames/catalog"),
        ("get", "/api/v1/endgames/mine"),
        ("get", "/api/v1/endgames/tablebase?fen=8/8/8/4k3/8/8/8/R3K3%20w%20-%20-%200%201"),
        ("post", "/api/v1/endgames/attempts"),
    ],
)
async def test_requires_login(settings: Settings, edb: Database, method: str, path: str) -> None:
    async with client_with(settings, anonymous=True) as ac:
        response = await getattr(ac, method)(path)
    assert response.status_code == 401
