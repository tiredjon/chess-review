"""`GET /insights/me`: выводы на фикстурных партиях, примеры, тренировки, изоляция."""

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Color, Game, GameSource, Move, Puzzle, User
from app.db.session import Database
from app.review.types import MoveClass, Phase
from tests.conftest import api_client

pytestmark = pytest.mark.integration

WHITE_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 {n}"
BLACK_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 2 {n}"


def _motifs(*, played: Sequence[str] = (), missed: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "played": [{"type": kind} for kind in played],
        "missed": [{"type": kind} for kind in missed],
        "refutation": [],
        "sacrifice": None,
    }


def _move(
    ply: int,
    cls: MoveClass,
    *,
    uci: str = "e2e4",
    best: str = "e2e4",
    before: float = 50.0,
    after: float = 50.0,
    motifs: dict[str, Any] | None = None,
    phase: Phase = Phase.MIDDLEGAME,
) -> Move:
    white = ply % 2 == 1
    return Move(
        ply=ply,
        san=f"m{ply}",
        uci=uci,
        best_uci=best,
        best_san=f"b{ply}",
        fen_before=(WHITE_FEN if white else BLACK_FEN).format(n=(ply + 1) // 2),
        win_before=before,
        win_after=after,
        accuracy=50.0,
        move_class=cls,
        motifs=motifs or _motifs(),
        phase=phase,
    )


def _game(user_id: uuid.UUID, name: str, *, day: int, family: str, result: str) -> Game:
    return Game(
        user_id=user_id,
        source=GameSource.CHESSCOM,
        external_id=f"{user_id}-{name}",
        pgn="*",
        white="me",
        black=name,
        result=result,
        time_control="600",
        played_at=datetime(2026, 1, 1 + day % 28, day // 28, tzinfo=UTC),
        user_color=Color.WHITE,
        opening_eco="C00" if family == "French Defense" else "C50",
        opening_name=f"{family}: Some Variation",
    )


async def _seed(
    db: Database, user_id: uuid.UUID, *, analyzed: int, puzzles: int
) -> list[uuid.UUID]:
    """`analyzed` разобранных проигранных партий во французской белыми: в каждой упущена вилка
    (ход 1), взята висящая фигура и связка (ходы 3, 5 — лучшие, позиция выиграна) и зевок
    в выигранном эндшпиле (ход 7); ход соперника с ошибкой не считается. Плюс 12 выигранных
    партий в итальянской без анализа (база для дебютов) и `puzzles` пазлов на вилку."""
    ids = []
    async with db.sessionmaker() as session:
        for i in range(analyzed):
            g = _game(user_id, f"fr{i}", day=i, family="French Defense", result="0-1")
            session.add(g)
            await session.flush()
            ids.append(g.id)
            session.add(
                Analysis(
                    game_id=g.id,
                    depth=10,
                    status=AnalysisStatus.DONE,
                    moves=[
                        _move(
                            1,
                            MoveClass.MISTAKE,
                            best="d2d4",
                            after=35,
                            motifs=_motifs(missed=["fork"]),
                        ),
                        _move(2, MoveClass.BLUNDER, before=65, after=15),
                        _move(
                            3, MoveClass.BEST, after=85, motifs=_motifs(played=["hanging_piece"])
                        ),
                        _move(
                            5, MoveClass.BEST, before=85, after=85, motifs=_motifs(played=["pin"])
                        ),
                        _move(
                            7,
                            MoveClass.BLUNDER,
                            best="d2d4",
                            before=85,
                            after=20,
                            phase=Phase.ENDGAME,
                        ),
                    ],
                )
            )
        for i in range(12):
            session.add(_game(user_id, f"it{i}", day=40 + i, family="Italian Game", result="1-0"))
        await session.flush()
        source = (
            await session.execute(
                select(Move.id, Move.fen_before)
                .join(Analysis, Analysis.id == Move.analysis_id)
                .where(Analysis.game_id.in_(ids), Move.ply == 1)
                .order_by(Move.id)
            )
        ).all()
        for row in source[:puzzles]:
            session.add(
                Puzzle(
                    user_id=user_id,
                    move_id=row.id,
                    fen=f"{row.fen_before}#{row.id}",
                    solution_uci=["d2d4"],
                    themes=["fork"],
                )
            )
        await session.commit()
    return ids


@pytest.fixture
async def stranger(
    db: Database, settings: Settings
) -> AsyncIterator[tuple[uuid.UUID, AsyncClient]]:
    async with db.sessionmaker() as session:
        user = User(email=f"stranger-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(user)
        await session.commit()
    async with api_client(settings, user.id) as client:
        yield user.id, client


def _by_id(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in body["findings"]}


async def test_findings(db: Database, settings: Settings) -> None:
    games = await _seed(db, settings.default_user_id, analyzed=12, puzzles=3)
    async with api_client(settings) as client:
        response = await client.get("/api/v1/insights/me")
    assert response.status_code == 200
    body = response.json()
    assert body["filters"] == {"source": None, "time_class": None}
    assert body["analyzed_games"] == 12
    assert body["min_games"] == 10
    findings = _by_id(body)
    assert set(findings) == {"motif:fork", "opening:white:French Defense", "conversion:winning"}

    fork = findings["motif:fork"]
    assert fork["kind"] == "motif"
    assert fork["key"] == "fork"
    # 12 упущенных вилок из 12 против 0 из 24 по висящей фигуре и связке.
    assert fork["stats"] == {"value": 100.0, "baseline": 0.0, "count": 12, "total": 12}
    assert fork["severity"] == "high"
    assert fork["train"] == {
        "kind": "puzzles",
        "query": {"theme": "fork", "phase": None, "eco": None},
        "available": 3,
    }

    opening = findings["opening:white:French Defense"]
    assert opening["stats"] == {"value": 0.0, "baseline": 100.0, "count": 12, "total": 24}
    assert opening["train"]["kind"] == "course"
    assert opening["train"]["query"]["eco"] == "C00"
    # Первая ошибка партии в этом дебюте.
    assert {e["ply"] for e in opening["examples"]} == {1}

    conversion = findings["conversion:winning"]
    assert conversion["stats"] == {"value": 100.0, "baseline": 15.0, "count": 12, "total": 12}
    assert conversion["train"] == {
        "kind": "endgames",
        "query": {"theme": None, "phase": None, "eco": None},
        "available": 12,
    }
    assert {e["ply"] for e in conversion["examples"]} == {7}

    # Порядок — по важности, затем по score.
    order = {"high": 0, "medium": 1, "low": 2}
    keys = [(order[f["severity"]], -f["score"]) for f in body["findings"]]
    assert keys == sorted(keys)

    # Примеры: ≤ 5, из разных партий, свежие первыми, ход пользователя.
    examples = fork["examples"]
    assert len(examples) == 5
    assert len({e["game_id"] for e in examples}) == 5
    assert {e["game_id"] for e in examples} <= {str(g) for g in games}
    played = [e["played_at"] for e in examples]
    assert played == sorted(played, reverse=True)
    first = examples[0]
    assert first["ply"] == 1
    assert first["san"] == "m1"
    assert first["best_san"] == "b1"
    assert first["move_class"] == "mistake"
    assert first["fen_before"].split()[1] == "w"
    assert first["opponent"] == "fr11"


async def test_below_min_games(db: Database, settings: Settings) -> None:
    await _seed(db, settings.default_user_id, analyzed=9, puzzles=0)
    async with api_client(settings) as client:
        body = (await client.get("/api/v1/insights/me")).json()
    assert body["analyzed_games"] == 9
    assert body["findings"] == []


async def test_filters(db: Database, settings: Settings) -> None:
    await _seed(db, settings.default_user_id, analyzed=12, puzzles=0)
    async with api_client(settings) as client:
        rapid = (await client.get("/api/v1/insights/me?time_class=rapid")).json()
        blitz = (await client.get("/api/v1/insights/me?time_class=blitz")).json()
        lichess = (await client.get("/api/v1/insights/me?source=lichess")).json()
        bad = await client.get("/api/v1/insights/me?source=fide")
    assert rapid["analyzed_games"] == 12
    assert rapid["findings"]
    assert rapid["filters"] == {"source": None, "time_class": "rapid"}
    assert blitz["analyzed_games"] == 0
    assert blitz["findings"] == []
    assert lichess["filters"]["source"] == "lichess"
    assert lichess["findings"] == []
    assert bad.status_code == 422


async def test_empty(db: Database, settings: Settings) -> None:
    async with api_client(settings) as client:
        body = (await client.get("/api/v1/insights/me")).json()
    assert body == {
        "filters": {"source": None, "time_class": None},
        "analyzed_games": 0,
        "min_games": 10,
        "findings": [],
    }


async def test_isolation(
    db: Database, settings: Settings, stranger: tuple[uuid.UUID, AsyncClient]
) -> None:
    """Выводы, примеры и число пазлов — только по своим партиям."""
    stranger_id, stranger_client = stranger
    mine = await _seed(db, settings.default_user_id, analyzed=12, puzzles=3)
    # У чужого — свои 10 партий и 1 пазл.
    theirs = await _seed(db, stranger_id, analyzed=10, puzzles=1)

    their_body = (await stranger_client.get("/api/v1/insights/me")).json()
    assert their_body["analyzed_games"] == 10
    their = _by_id(their_body)
    assert their["motif:fork"]["train"]["available"] == 1
    assert their["motif:fork"]["stats"]["total"] == 10
    assert their["opening:white:French Defense"]["stats"]["total"] == 22
    for finding in their.values():
        assert {e["game_id"] for e in finding["examples"]} <= {str(g) for g in theirs}

    async with api_client(settings) as client:
        my_body = (await client.get("/api/v1/insights/me")).json()
    assert my_body["analyzed_games"] == 12
    my = _by_id(my_body)
    assert my["motif:fork"]["train"]["available"] == 3
    assert my["conversion:winning"]["train"]["available"] == 12
    for finding in my.values():
        assert {e["game_id"] for e in finding["examples"]} <= {str(g) for g in mine}


async def test_requires_auth(settings: Settings) -> None:
    async with api_client(settings, anonymous=True) as client:
        response = await client.get("/api/v1/insights/me")
    assert response.status_code == 401
