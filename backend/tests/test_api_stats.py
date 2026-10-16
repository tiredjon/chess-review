"""Статистика: агрегаты на фикстурных партиях с заранее посчитанными числами."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import literal, select

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Color, Game, GameSource, Move
from app.db.session import Database
from app.review.game_rating import time_class
from app.review.types import MoveClass, Phase
from app.stats.queries import time_class_sql

pytestmark = pytest.mark.integration

WHITE_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 {n}"
BLACK_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 {n}"


def move(ply: int, cls: MoveClass, *, miss: bool = False, motifs: Any = None) -> Move:
    white = ply % 2 == 1
    return Move(
        ply=ply,
        san=f"m{ply}",
        uci="e2e4",
        fen_before=(WHITE_FEN if white else BLACK_FEN).format(n=(ply + 1) // 2),
        win_before=50.0,
        win_after=40.0,
        accuracy=80.0,
        move_class=cls,
        is_miss=miss,
        motifs=motifs,
        phase=Phase.MIDDLEGAME,
    )


def motifs(refutation: list[str], missed: list[str]) -> dict[str, Any]:
    return {
        "played": [],
        "missed": [{"type": kind} for kind in missed],
        "refutation": [{"type": kind} for kind in refutation],
        "sacrifice": None,
    }


def game(
    user_id: uuid.UUID,
    name: str,
    *,
    source: GameSource = GameSource.CHESSCOM,
    color: Color | None,
    result: str,
    tc: str | None,
    day: int,
    opening: tuple[str, str] | None = None,
    official: float | None = None,
) -> Game:
    return Game(
        user_id=user_id,
        source=source,
        external_id=name,
        pgn="*",
        white="me" if color == Color.WHITE else name,
        black="me" if color == Color.BLACK else name,
        result=result,
        time_control=tc,
        played_at=datetime(2026, 1, day, tzinfo=UTC),
        user_color=color,
        opening_eco=opening[0] if opening else None,
        opening_name=opening[1] if opening else None,
        source_white_accuracy=official if color == Color.WHITE else None,
        source_black_accuracy=official if color == Color.BLACK else None,
    )


ITALIAN = ("C50", "Italian Game")
SICILIAN = ("B20", "Sicilian Defense")


@pytest.fixture
async def games(db: Database, settings: Settings) -> dict[str, uuid.UUID]:
    """A: белые, победа, рапид, официальная 80 (наша 70 не берётся), ошибки с мотивами.
    B: Lichess, чёрные, победа, блиц, наша 60. C: PGN без цвета. D: чёрные, поражение,
    пуля, без анализа. E: белые, ничья, без контроля (рапид), старый анализ без cc —
    точность по Lichess 50."""
    uid = settings.default_user_id
    a = game(
        uid, "A", color=Color.WHITE, result="1-0", tc="600", day=1, opening=ITALIAN, official=80
    )
    b = game(
        uid,
        "B",
        source=GameSource.LICHESS,
        color=Color.BLACK,
        result="0-1",
        tc="180+2",
        day=2,
        opening=SICILIAN,
    )
    c = game(uid, "C", source=GameSource.PGN, color=None, result="1-0", tc=None, day=3)
    d = game(uid, "D", color=Color.BLACK, result="1-0", tc="60", day=4, opening=SICILIAN)
    e = game(uid, "E", color=Color.WHITE, result="1/2-1/2", tc=None, day=5, opening=ITALIAN)
    async with db.sessionmaker() as session:
        session.add_all([a, b, c, d, e])
        await session.flush()
        session.add_all(
            [
                Analysis(
                    game_id=a.id,
                    depth=10,
                    status=AnalysisStatus.DONE,
                    cc_white_accuracy=70,
                    phase_accuracy={"white": {"opening": 90, "middlegame": 70, "endgame": None}},
                    moves=[
                        move(1, MoveClass.BEST),
                        move(2, MoveClass.BLUNDER, motifs=motifs(["skewer"], [])),
                        move(3, MoveClass.MISTAKE, motifs=motifs(["fork"], ["fork", "pin"])),
                        move(4, MoveClass.BEST),
                        move(
                            5,
                            MoveClass.BLUNDER,
                            miss=True,
                            motifs=motifs(["hanging_piece"], ["fork"]),
                        ),
                    ],
                ),
                Analysis(
                    game_id=b.id,
                    depth=10,
                    status=AnalysisStatus.DONE,
                    cc_black_accuracy=60,
                    phase_accuracy={"black": {"opening": 80, "middlegame": 60, "endgame": 50}},
                    moves=[
                        move(1, MoveClass.BLUNDER),
                        move(2, MoveClass.GREAT, motifs=motifs([], ["pin"])),
                    ],
                ),
                Analysis(game_id=e.id, depth=10, status=AnalysisStatus.DONE, white_accuracy=50),
            ]
        )
        await session.commit()
    return {"A": a.id, "B": b.id, "C": c.id, "D": d.id, "E": e.id}


async def get_stats(client: AsyncClient, **params: str) -> dict[str, Any]:
    response = await client.get("/api/v1/stats/me", params=params)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_totals_and_accuracy(client: AsyncClient, games: dict[str, uuid.UUID]) -> None:
    stats = await get_stats(client)

    assert stats["totals"] == {
        "games": 4,
        "games_without_color": 1,
        "analyzed": 3,
        "wins": 2,
        "draws": 1,
        "losses": 1,
        "accuracy": pytest.approx(190 / 3),
        "with_accuracy": 3,
    }
    points = stats["accuracy"]["points"]
    assert [p["game_id"] for p in points] == [str(games[k]) for k in "ABE"]
    assert [p["accuracy"] for p in points] == [80, 60, 50]
    assert [p["kind"] for p in points] == ["official", "cc", "lichess"]
    assert [p["moving_avg"] for p in points] == pytest.approx([80, 70, 190 / 3])
    assert [p["time_class"] for p in points] == ["rapid", "blitz", "rapid"]
    assert [p["outcome"] for p in points] == ["win", "win", "draw"]
    assert points[0]["opponent"] == "A"


async def test_openings_phases_classes(client: AsyncClient, games: dict[str, uuid.UUID]) -> None:
    stats = await get_stats(client)

    assert stats["openings"] == {
        "white": [
            {
                "eco": "C50",
                "name": "Italian Game",
                "games": 2,
                "wins": 1,
                "draws": 1,
                "losses": 0,
                "accuracy": 65.0,
            },
        ],
        "black": [
            {
                "eco": "B20",
                "name": "Sicilian Defense",
                "games": 2,
                "wins": 1,
                "draws": 0,
                "losses": 1,
                "accuracy": 60.0,
            },
        ],
    }
    assert stats["phases"] == [
        {"phase": "opening", "accuracy": 85.0, "games": 2},
        {"phase": "middlegame", "accuracy": 65.0, "games": 2},
        {"phase": "endgame", "accuracy": 50.0, "games": 1},
    ]
    classes = {item["class"]: item for item in stats["classes"]["items"]}
    assert (stats["classes"]["games"], stats["classes"]["moves"]) == (3, 4)
    # Только ходы пользователя: белые в A (best, mistake, blunder+miss), чёрные в B (great).
    assert {k: v["count"] for k, v in classes.items() if v["count"]} == {
        "best": 1,
        "mistake": 1,
        "blunder": 1,
        "great": 1,
        "miss": 1,
    }
    assert classes["best"]["per_game"] == pytest.approx(0.33)
    assert classes["best"]["share"] == 25.0


async def test_error_motifs(client: AsyncClient, games: dict[str, uuid.UUID]) -> None:
    stats = await get_stats(client)

    # fork: опровержение и упущение одного хода — один раз; skewer — ход соперника,
    # pin в B — у хорошего хода, не ошибки.
    assert [(m["type"], m["count"]) for m in stats["motifs"]] == [
        ("fork", 2),
        ("hanging_piece", 1),
        ("pin", 1),
    ]
    examples = stats["motifs"][0]["examples"]
    assert [(e["ply"], e["class"], e["fullmove"], e["color"]) for e in examples] == [
        (3, "mistake", 2, "white"),
        (5, "blunder", 3, "white"),
    ]
    assert examples[0]["game_id"] == str(games["A"])


async def test_filters(client: AsyncClient, games: dict[str, uuid.UUID]) -> None:
    lichess = await get_stats(client, source="lichess")
    rapid = await get_stats(client, time_class="rapid")
    bullet = await get_stats(client, time_class="bullet", source="chesscom")

    assert lichess["totals"]["games"] == 1
    assert lichess["filters"] == {"source": "lichess", "time_class": None}
    assert (rapid["totals"]["games"], rapid["totals"]["games_without_color"]) == (2, 1)
    assert bullet["totals"]["games"] == 1
    assert bullet["accuracy"]["points"] == []


async def test_empty_stats(client: AsyncClient, db: Database) -> None:
    stats = await get_stats(client)

    assert stats["totals"]["games"] == 0
    assert stats["totals"]["accuracy"] is None
    assert stats["phases"][0] == {"phase": "opening", "accuracy": None, "games": 0}
    assert stats["motifs"] == []
    assert stats["classes"]["items"][0]["per_game"] == 0.0


async def test_invalid_filter(client: AsyncClient, db: Database) -> None:
    response = await client.get("/api/v1/stats/me", params={"time_class": "classical"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "tc",
    [
        "600",
        "180+2",
        "60",
        "60+1",
        "120+1",
        "300+3",
        "1800+20",
        "0+1",
        "179",
        "1/86400",
        "",
        "-",
        "?",
        None,
        "600+0",
        "abc",
        "5+5+5",
    ],
)
async def test_time_class_sql_matches_python(db: Database, tc: str | None) -> None:
    async with db.sessionmaker() as session:
        value = await session.scalar(select(time_class_sql(literal(tc))))

    assert value == time_class(tc)
