"""Пазлы в БД: генерация из анализа (идемпотентно), выдача, попытки, расписание."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import chess
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, update

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Color, Game, GameSource, Move, Puzzle
from app.db.session import Database
from app.puzzles.generate import generate_puzzles
from app.review.types import MoveClass, Phase
from app.workers import analysis as worker
from tests.test_analyzer import FakeEngine
from tests.test_api_analysis import OPERA
from tests.test_puzzles import (
    BACK_RANK,
    FORK,
    FORK_LINE,
    FakeAnalyser,
    after,
    engine_line,
    line_json,
    lines,
)

pytestmark = pytest.mark.integration

# Позиция перед вилкой: чёрные сходили Kf8-e8 (ход соперника перед ошибкой).
BEFORE_FORK = "r4k2/8/8/3N4/8/8/8/4K3 b - - 0 1"


def row(ply: int, fen: str, uci: str, cls: MoveClass, **extra: Any) -> Move:
    board = chess.Board(fen)
    return Move(
        ply=ply,
        san=board.san(chess.Move.from_uci(uci)),
        uci=uci,
        fen_before=fen,
        win_before=80.0,
        win_after=40.0,
        accuracy=30.0,
        move_class=cls,
        phase=Phase.MIDDLEGAME,
        **extra,
    )


def fork_moves() -> list[Move]:
    """Ход 1… Ke8 соперника, затем 2. Ke2?? вместо вилки Nc7+ и ответ чёрных."""
    return [
        row(1, BEFORE_FORK, "f8e8", MoveClass.BEST),
        row(
            2,
            FORK,
            "e1e2",
            MoveClass.BLUNDER,
            best_uci="d5c7",
            best_san="Nc7+",
            pv=line_json(FORK, FORK_LINE),
            multipv=[engine_line(FORK, FORK_LINE, cp=520)],
            motifs={"played": [], "missed": [{"type": "fork"}], "refutation": []},
        ),
        # Ошибка соперника — не пазл пользователя.
        row(
            3,
            after(FORK, ["e1e2"]),
            "e8d8",
            MoveClass.BLUNDER,
            best_uci="e8d7",
            pv=line_json(after(FORK, ["e1e2"]), ["e8d7"]),
        ),
    ]


def fork_analyser() -> FakeAnalyser:
    return FakeAnalyser(
        {
            FORK: lines((["d5c7"], 520), (["e1e2"], 0)),
            after(FORK, ["d5c7", "e8d7"]): lines((["c7a8"], 520), (["c7e6"], 0)),
        }
    )


async def add_analysis(db: Database, game_id: uuid.UUID, moves: list[Move]) -> uuid.UUID:
    async with db.sessionmaker() as session:
        analysis = Analysis(game_id=game_id, depth=10, status=AnalysisStatus.DONE, moves=moves)
        session.add(analysis)
        await session.commit()
        return analysis.id


@pytest.fixture
async def fork_game(db: Database, settings: Settings) -> uuid.UUID:
    async with db.sessionmaker() as session:
        game = Game(
            user_id=settings.default_user_id,
            source=GameSource.LICHESS,
            external_id="fork",
            pgn="*",
            white="me",
            black="Rival",
            result="0-1",
            played_at=datetime(2026, 5, 1, tzinfo=UTC),
            user_color=Color.WHITE,
        )
        session.add(game)
        await session.commit()
        return game.id


async def puzzles(db: Database) -> list[Puzzle]:
    async with db.sessionmaker() as session:
        return list(await session.scalars(select(Puzzle)))


async def test_generation_is_idempotent(db: Database, fork_game: uuid.UUID) -> None:
    analysis_id = await add_analysis(db, fork_game, fork_moves())

    assert await generate_puzzles(db, fork_analyser(), analysis_id) == 1
    assert await generate_puzzles(db, fork_analyser(), analysis_id) == 1

    (puzzle,) = await puzzles(db)
    assert puzzle.fen == FORK
    assert puzzle.solution_uci == ["d5c7", "e8d7", "c7a8"]
    assert puzzle.themes == ["fork"]
    assert puzzle.next_review_at is None

    # Повторный анализ партии: тот же пазл, ссылка — на ход нового анализа.
    again = await add_analysis(db, fork_game, fork_moves())
    await generate_puzzles(db, fork_analyser(), again)
    (puzzle,) = await puzzles(db)
    async with db.sessionmaker() as session:
        move = await session.get(Move, puzzle.move_id)
    assert move is not None
    assert move.analysis_id == again


async def test_no_puzzles_for_skipped_users(
    db: Database, fork_game: uuid.UUID, settings: Settings
) -> None:
    """Партии системного пользователя бота пазлов не дают."""
    analysis_id = await add_analysis(db, fork_game, fork_moves())

    count = await generate_puzzles(
        db, fork_analyser(), analysis_id, skip_users=(settings.default_user_id,)
    )

    assert count == 0
    assert await puzzles(db) == []


async def test_no_puzzles_without_user_color(db: Database, fork_game: uuid.UUID) -> None:
    async with db.sessionmaker() as session:
        await session.execute(update(Game).values(user_color=None))
        await session.commit()
    analysis_id = await add_analysis(db, fork_game, fork_moves())

    assert await generate_puzzles(db, fork_analyser(), analysis_id) == 0


async def test_worker_generates_puzzles_after_analysis(
    client: AsyncClient,
    db: Database,
    redis: Redis,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Задача анализа после сохранения разбора генерирует пазлы, а повтор уже готовой
    задачи (прерванной на генерации) — генерирует снова; сбой генерации анализ не валит."""
    calls: list[uuid.UUID] = []

    async def fake_generate(
        _db: Database, _analyser: object, analysis_id: uuid.UUID, **_: object
    ) -> int:
        calls.append(analysis_id)
        raise RuntimeError("движок упал")

    monkeypatch.setattr(worker, "generate_puzzles", fake_generate)
    (game,) = (await client.post("/api/v1/games/pgn", json={"pgn": OPERA})).json()
    analysis = (await client.post(f"/api/v1/games/{game['id']}/analyze", json={"depth": 6})).json()
    ctx = {
        "settings": settings,
        "db": db,
        "redis": redis,
        "engine": FakeEngine(),
        "engine_version": "Fake 1.0",
    }

    assert await worker.analyze_game(ctx, analysis["id"]) == "done"
    assert await worker.analyze_game(ctx, analysis["id"]) == "done"
    assert calls == [uuid.UUID(analysis["id"])] * 2


@pytest.fixture
async def puzzle_ids(
    db: Database, fork_game: uuid.UUID, settings: Settings
) -> dict[str, uuid.UUID]:
    """Пазл с вилкой (из партии) и новый пазл с матом (без партии)."""
    analysis_id = await add_analysis(db, fork_game, fork_moves())
    await generate_puzzles(db, fork_analyser(), analysis_id)
    async with db.sessionmaker() as session:
        mate = Puzzle(
            user_id=settings.default_user_id,
            fen=BACK_RANK,
            solution_uci=["a1a8"],
            themes=["mate_in_n"],
        )
        session.add(mate)
        await session.commit()
        fork = await session.scalar(select(Puzzle.id).where(Puzzle.fen == FORK))
    assert fork is not None
    return {"fork": fork, "mate": mate.id}


async def next_puzzle(client: AsyncClient, **params: Any) -> dict[str, Any]:
    response = await client.get("/api/v1/puzzles/next", params=params)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def attempt(client: AsyncClient, puzzle_id: uuid.UUID, **body: Any) -> dict[str, Any]:
    response = await client.post(f"/api/v1/puzzles/{puzzle_id}/attempt", json=body)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_next_returns_new_puzzle_with_source(
    client: AsyncClient, puzzle_ids: dict[str, uuid.UUID], fork_game: uuid.UUID
) -> None:
    data = await next_puzzle(client)

    puzzle = data["puzzle"]
    # Новые — сначала из партий (по дате партии), пазл без партии — в конце.
    assert puzzle["id"] == str(puzzle_ids["fork"])
    assert puzzle["color"] == "white"
    assert puzzle["player_moves"] == 2
    assert puzzle["hints"] == ["d5", "c7"]
    assert puzzle["last_move"] == {"uci": "f8e8", "san": "Ke8", "fen_before": BEFORE_FORK}
    assert puzzle["source"] | {"played_at": None} == {
        "game_id": str(fork_game),
        "ply": 2,
        "fullmove": 1,
        "san": "Ke2",
        "class": "blunder",
        "is_miss": False,
        "opponent": "Rival",
        "played_at": None,
    }
    assert "solution_uci" not in puzzle
    assert data["counts"] == {"due": 0, "new": 2, "total": 2, "streak": 0, "next_review_at": None}

    skipped = await next_puzzle(client, exclude=[str(puzzle_ids["fork"])])
    assert skipped["puzzle"]["id"] == str(puzzle_ids["mate"])
    assert skipped["puzzle"]["source"] is None
    assert skipped["puzzle"]["last_move"] is None


async def test_solve_step_by_step(client: AsyncClient, puzzle_ids: dict[str, uuid.UUID]) -> None:
    fork = puzzle_ids["fork"]

    step = await attempt(client, fork, moves_uci=["d5c7"])
    assert step == {
        "result": "continue",
        "reply_uci": "e8d7",
        "expected_uci": None,
        "solution_uci": None,
        "solution_san": None,
        "box": None,
        "next_review_at": None,
        "streak": None,
    }
    started = datetime.now(UTC)
    done = await attempt(client, fork, moves_uci=["d5c7", "e8d7", "c7a8"])

    assert done["result"] == "solved"
    assert done["solution_san"] == ["Nc7+", "Kd7", "Nxa8"]
    assert done["box"] == 1
    assert done["streak"] == 1
    review = datetime.fromisoformat(done["next_review_at"])
    assert started + timedelta(days=1) <= review <= datetime.now(UTC) + timedelta(days=1)

    # Решённый пазл уходит в расписание: дальше выдаётся оставшийся новый.
    data = await next_puzzle(client)
    assert data["puzzle"]["id"] == str(puzzle_ids["mate"])
    assert data["counts"]["new"] == 1
    assert data["counts"]["next_review_at"] == done["next_review_at"]


async def test_failed_attempt_repeats_soon(
    client: AsyncClient, db: Database, puzzle_ids: dict[str, uuid.UUID]
) -> None:
    mate = puzzle_ids["mate"]
    await attempt(client, puzzle_ids["fork"], moves_uci=["d5c7", "e8d7", "c7a8"], hint_used=True)

    failed = await attempt(client, mate, moves_uci=["a1a7"])

    assert failed["result"] == "failed"
    assert failed["expected_uci"] == "a1a8"
    assert failed["solution_uci"] == ["a1a8"]
    assert (failed["box"], failed["streak"]) == (0, 0)
    async with db.sessionmaker() as session:
        puzzle = await session.get(Puzzle, mate)
        hinted = await session.get(Puzzle, puzzle_ids["fork"])
    assert puzzle is not None
    assert hinted is not None
    assert (puzzle.attempts, puzzle.solved) == (1, False)
    assert hinted.box == 1

    # Через 10 минут — пора повторить, и он идёт раньше новых.
    async with db.sessionmaker() as session:
        await session.execute(
            update(Puzzle)
            .where(Puzzle.id == mate)
            .values(next_review_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    data = await next_puzzle(client)
    assert data["puzzle"]["id"] == str(mate)
    assert data["counts"]["due"] == 1


async def test_give_up(client: AsyncClient, puzzle_ids: dict[str, uuid.UUID]) -> None:
    result = await attempt(client, puzzle_ids["fork"], moves_uci=["d5c7"], gave_up=True)

    assert (result["result"], result["expected_uci"]) == ("failed", "c7a8")


async def test_streak_counts_since_last_failure(
    client: AsyncClient, puzzle_ids: dict[str, uuid.UUID]
) -> None:
    await attempt(client, puzzle_ids["mate"], moves_uci=["a1a7"])
    await attempt(client, puzzle_ids["mate"], moves_uci=["a1a8"])
    last = await attempt(client, puzzle_ids["fork"], moves_uci=["d5c7", "e8d7", "c7a8"])

    assert last["streak"] == 2


@pytest.mark.parametrize(
    "body",
    [
        {"moves_uci": ["d5c7", "e8e7"]},
        {"moves_uci": ["e1e1"]},
        {"moves_uci": []},
        {"moves_uci": ["z9"]},
    ],
)
async def test_invalid_attempt(
    client: AsyncClient, puzzle_ids: dict[str, uuid.UUID], body: dict[str, Any]
) -> None:
    response = await client.post(f"/api/v1/puzzles/{puzzle_ids['fork']}/attempt", json=body)

    assert response.status_code == 422


async def test_unknown_puzzle(client: AsyncClient, db: Database) -> None:
    response = await client.post(
        f"/api/v1/puzzles/{uuid.uuid4()}/attempt", json={"moves_uci": ["e2e4"]}
    )

    assert response.status_code == 404


async def test_no_puzzles(client: AsyncClient, db: Database) -> None:
    data = await next_puzzle(client)

    assert data["puzzle"] is None
    assert data["counts"]["total"] == 0


async def test_attempts_are_counted(
    client: AsyncClient, db: Database, puzzle_ids: dict[str, uuid.UUID]
) -> None:
    await attempt(client, puzzle_ids["fork"], moves_uci=["d5c7"])
    async with db.sessionmaker() as session:
        attempts = await session.scalar(select(func.sum(Puzzle.attempts)))

    # Промежуточный верный ход попыткой не считается.
    assert attempts == 0
