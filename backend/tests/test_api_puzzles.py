"""Пазлы в БД: генерация из анализа (идемпотентно), выдача, попытки, расписание."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import chess
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update

from app.core.config import Settings
from app.db.models import (
    Analysis,
    AnalysisStatus,
    Color,
    Game,
    GameSource,
    Move,
    Puzzle,
    PuzzleAttempt,
    PuzzleRushRun,
    User,
)
from app.db.session import Database
from app.puzzles.generate import generate_puzzles
from app.review.types import MoveClass, Phase
from app.workers import analysis as worker
from tests.conftest import api_client
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


# --- Сессия 16.2: режимы, фильтры, темы, забеги ---

NOW = datetime(2026, 6, 1, tzinfo=UTC)
# Третья позиция: решение из пяти ходов (длиннее остальных), сами ходы в этих тестах не играются.
LONG_FEN = "4k3/8/8/8/8/8/8/R3K3 w Q - 0 1"


@pytest.fixture(autouse=True)
async def clean_rush_runs(db: Database) -> None:
    """Забеги не удаляются вместе с пазлами и партиями (`db` их не трогает)."""
    async with db.sessionmaker() as session:
        await session.execute(delete(PuzzleRushRun))
        await session.commit()


async def add_game(
    db: Database, user_id: uuid.UUID, name: str, *, eco: str | None, phase: Phase, days: int
) -> int:
    """Партия с анализом и одним ходом (ply 2) в заданной фазе; id хода."""
    async with db.sessionmaker() as session:
        game = Game(
            user_id=user_id,
            source=GameSource.LICHESS,
            external_id=name,
            pgn="*",
            white="me",
            black="Rival",
            result="0-1",
            played_at=NOW - timedelta(days=days),
            user_color=Color.WHITE,
            opening_eco=eco,
            opening_name=f"Дебют {eco}" if eco else None,
        )
        move = Move(
            ply=2,
            san="Ke2",
            uci="e1e2",
            fen_before=FORK,
            win_before=80.0,
            win_after=40.0,
            accuracy=30.0,
            move_class=MoveClass.BLUNDER,
            phase=phase,
        )
        session.add(Analysis(game=game, depth=10, status=AnalysisStatus.DONE, moves=[move]))
        await session.commit()
        return move.id


@pytest.fixture
async def trio(db: Database, settings: Settings) -> dict[str, uuid.UUID]:
    """Три пазла разной длины, фазы, дебюта и темы:

    - `mate` — решение из 1 хода, дебют, C50, тема mate_in_n;
    - `fork` — 3 хода, миттельшпиль, B90, тема fork;
    - `long` — 5 ходов, эндшпиль, без дебюта, темы fork и pin; решён, коробка 3.
    """
    user = settings.default_user_id
    opening = await add_game(db, user, "g-mate", eco="C50", phase=Phase.OPENING, days=1)
    middle = await add_game(db, user, "g-fork", eco="B90", phase=Phase.MIDDLEGAME, days=2)
    end = await add_game(db, user, "g-long", eco=None, phase=Phase.ENDGAME, days=3)
    async with db.sessionmaker() as session:
        mate = Puzzle(
            user_id=user,
            move_id=opening,
            fen=BACK_RANK,
            solution_uci=["a1a8"],
            themes=["mate_in_n"],
        )
        fork = Puzzle(
            user_id=user,
            move_id=middle,
            fen=FORK,
            solution_uci=["d5c7", "e8d7", "c7a8"],
            themes=["fork"],
        )
        long = Puzzle(
            user_id=user,
            move_id=end,
            fen=LONG_FEN,
            solution_uci=["a1a8", "e8d7", "a8a7", "d7e6", "a7a6"],
            themes=["fork", "pin"],
            solved=True,
            box=3,
            attempts=2,
            next_review_at=datetime.now(UTC) + timedelta(days=7),
        )
        session.add_all([mate, fork, long])
        await session.commit()
        return {"mate": mate.id, "fork": fork.id, "long": long.id}


async def walk(client: AsyncClient, **params: Any) -> list[str]:
    """Пазлы подряд, как это делает клиент: каждый показанный — в `exclude`."""
    seen: list[str] = []
    for _ in range(10):
        data = await next_puzzle(client, exclude=seen, **params)
        if data["puzzle"] is None:
            return seen
        seen.append(data["puzzle"]["id"])
    raise AssertionError("выдача не кончается")


async def test_srs_is_default_and_skips_not_due(
    client: AsyncClient, trio: dict[str, uuid.UUID]
) -> None:
    """Без `mode` — как раньше: решённый пазл с будущим повторением не выдаётся."""
    explicit = await walk(client, mode="srs")

    assert await walk(client) == explicit
    assert set(explicit) == {str(trio["mate"]), str(trio["fork"])}


async def test_practice_puts_unsolved_first_and_never_repeats(
    client: AsyncClient, db: Database, trio: dict[str, uuid.UUID]
) -> None:
    order = await walk(client, mode="practice")

    # Нерешённые (свежие партии первыми), решённый с высокой коробкой — последним, хотя
    # повторение у него назначено на потом: practice на срок не смотрит.
    assert order == [str(trio["mate"]), str(trio["fork"]), str(trio["long"])]

    # Среди нерешённых — низкая коробка раньше высокой.
    async with db.sessionmaker() as session:
        await session.execute(update(Puzzle).where(Puzzle.id == trio["mate"]).values(box=4))
        await session.commit()
    assert (await walk(client, mode="practice"))[:2] == [str(trio["fork"]), str(trio["mate"])]


async def test_practice_prefers_least_recently_tried(
    client: AsyncClient, db: Database, trio: dict[str, uuid.UUID]
) -> None:
    async with db.sessionmaker() as session:
        await session.execute(
            update(Puzzle)
            .where(Puzzle.id == trio["mate"])
            .values(attempts=1, last_attempt_at=datetime.now(UTC))
        )
        await session.commit()

    # Одинаковая коробка и оба нерешённые: ни разу не решавшийся — раньше.
    assert (await walk(client, mode="practice"))[0] == str(trio["fork"])


async def test_rush_goes_from_short_solutions_to_long(
    client: AsyncClient, trio: dict[str, uuid.UUID]
) -> None:
    order = await walk(client, mode="rush")

    # Срок повторения и «решён» значения не имеют.
    assert order == [str(trio["mate"]), str(trio["fork"]), str(trio["long"])]


@pytest.mark.parametrize("mode", ["srs", "practice", "rush"])
async def test_theme_filter_in_every_mode(
    client: AsyncClient, trio: dict[str, uuid.UUID], mode: str
) -> None:
    ids = await walk(client, mode=mode, theme="fork")

    expected = {str(trio["fork"])} | ({str(trio["long"])} if mode != "srs" else set())
    assert set(ids) == expected


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"phase": "opening"}, ["mate"]),
        ({"phase": "middlegame"}, ["fork"]),
        ({"phase": "endgame"}, ["long"]),
        ({"eco": "B90"}, ["fork"]),
        ({"eco": "C50"}, ["mate"]),
        ({"theme": "pin"}, ["long"]),
        ({"theme": "fork", "phase": "middlegame"}, ["fork"]),
        ({"theme": "fork", "phase": "opening"}, []),
        ({"theme": "fork", "eco": "B90", "phase": "middlegame"}, ["fork"]),
        ({"eco": "B90", "phase": "opening"}, []),
        ({"theme": "skewer"}, []),
        ({"eco": "A00"}, []),
    ],
)
async def test_filters_combine(
    client: AsyncClient, trio: dict[str, uuid.UUID], params: dict[str, str], expected: list[str]
) -> None:
    assert await walk(client, mode="practice", **params) == [str(trio[k]) for k in expected]


async def test_counts_follow_filters(client: AsyncClient, trio: dict[str, uuid.UUID]) -> None:
    everything = await next_puzzle(client)
    forks = await next_puzzle(client, theme="fork")
    nothing = await next_puzzle(client, theme="skewer")

    assert (everything["counts"]["total"], everything["counts"]["new"]) == (3, 2)
    # Среди тем fork — `fork` (новый) и `long` (повторение в будущем).
    assert (forks["counts"]["total"], forks["counts"]["new"], forks["counts"]["due"]) == (2, 1, 0)
    assert nothing["puzzle"] is None
    assert nothing["counts"]["total"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"mode": "bogus"},
        {"phase": "midgame"},
        {"eco": "B 90"},
        {"eco": "B90B90B90"},
        {"theme": "Fork"},
        {"theme": "fork; drop"},
    ],
)
async def test_next_validates_params(client: AsyncClient, params: dict[str, str]) -> None:
    response = await client.get("/api/v1/puzzles/next", params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_practice_attempt_keeps_schedule_and_streak(
    client: AsyncClient, db: Database, trio: dict[str, uuid.UUID]
) -> None:
    await attempt(client, trio["fork"], moves_uci=["d5c7", "e8d7", "c7a8"], mode="srs")
    async with db.sessionmaker() as session:
        before = await session.get(Puzzle, trio["fork"])
    assert before is not None

    wrong = await attempt(client, trio["fork"], moves_uci=["d5b6"], mode="practice")
    right = await attempt(client, trio["mate"], moves_uci=["a1a8"], mode="practice")

    assert wrong["result"] == "failed"
    # В `failed` из practice коробка и дата — прежние, серия по srs не сбита.
    assert wrong["box"] == before.box
    assert datetime.fromisoformat(wrong["next_review_at"]) == before.next_review_at
    assert wrong["streak"] == right["streak"] == 1
    assert (right["box"], right["next_review_at"]) == (0, None)
    async with db.sessionmaker() as session:
        fork = await session.get(Puzzle, trio["fork"])
        mate = await session.get(Puzzle, trio["mate"])
        modes = list(await session.scalars(select(PuzzleAttempt.mode).order_by(PuzzleAttempt.id)))
    assert fork is not None
    assert mate is not None
    assert (fork.box, fork.next_review_at) == (before.box, before.next_review_at)
    assert (fork.attempts, fork.solved) == (2, False)
    assert (mate.box, mate.next_review_at, mate.attempts, mate.solved) == (0, None, 1, True)
    assert modes == ["srs", "practice", "practice"]


async def test_rush_attempt_is_recorded_without_touching_srs(
    client: AsyncClient, db: Database, trio: dict[str, uuid.UUID]
) -> None:
    done = await attempt(client, trio["mate"], moves_uci=["a1a8"], mode="rush")

    assert (done["result"], done["box"], done["next_review_at"], done["streak"]) == (
        "solved",
        0,
        None,
        0,
    )
    async with db.sessionmaker() as session:
        row = (await session.execute(select(PuzzleAttempt.mode, PuzzleAttempt.correct))).one()
    assert tuple(row) == ("rush", True)
    # Пазл остался новым для повторения.
    assert (await next_puzzle(client, mode="srs"))["counts"]["new"] == 2


async def test_continue_in_practice_writes_nothing(
    client: AsyncClient, db: Database, trio: dict[str, uuid.UUID]
) -> None:
    step = await attempt(client, trio["fork"], moves_uci=["d5c7"], mode="practice")

    assert step["result"] == "continue"
    async with db.sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(PuzzleAttempt)) == 0


async def test_unknown_attempt_mode(client: AsyncClient, trio: dict[str, uuid.UUID]) -> None:
    response = await client.post(
        f"/api/v1/puzzles/{trio['mate']}/attempt", json={"moves_uci": ["a1a8"], "mode": "blitz"}
    )

    assert response.status_code == 422


async def test_themes_counts(client: AsyncClient, db: Database, trio: dict[str, uuid.UUID]) -> None:
    async with db.sessionmaker() as session:
        await session.execute(
            update(Puzzle)
            .where(Puzzle.id == trio["fork"])
            .values(next_review_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    response = await client.get("/api/v1/puzzles/themes")

    assert response.status_code == 200
    assert response.json() == {
        # fork — у двух пазлов (один решён, другой пора повторить), по убыванию числа.
        "themes": [
            {"theme": "fork", "total": 2, "due": 1, "solved": 1},
            {"theme": "mate_in_n", "total": 1, "due": 0, "solved": 0},
            {"theme": "pin", "total": 1, "due": 0, "solved": 1},
        ],
        "phases": [
            {"phase": "opening", "total": 1, "solved": 0},
            {"phase": "middlegame", "total": 1, "solved": 0},
            {"phase": "endgame", "total": 1, "solved": 1},
        ],
        "openings": [
            {"eco": "B90", "name": "Дебют B90", "total": 1},
            {"eco": "C50", "name": "Дебют C50", "total": 1},
        ],
    }


async def test_themes_empty(client: AsyncClient, db: Database) -> None:
    data = (await client.get("/api/v1/puzzles/themes")).json()

    assert data["themes"] == []
    assert data["openings"] == []
    # Фазы — всегда три, с нулями.
    assert [(p["phase"], p["total"]) for p in data["phases"]] == [
        ("opening", 0),
        ("middlegame", 0),
        ("endgame", 0),
    ]


async def post_run(client: AsyncClient, **body: Any) -> Any:
    payload = {"variant": "3min", "score": 0, "mistakes": 3, "duration_s": 100} | body
    return await client.post("/api/v1/puzzles/rush", json=payload)


async def solve_rush(client: AsyncClient, puzzle_id: uuid.UUID, times: int) -> None:
    for _ in range(times):
        await attempt(client, puzzle_id, moves_uci=["a1a8"], mode="rush")


async def test_rush_run_records_best_per_variant(
    client: AsyncClient, trio: dict[str, uuid.UUID]
) -> None:
    empty = await client.get("/api/v1/puzzles/rush", params={"variant": "3min"})
    assert empty.json() == {"best": None, "recent": []}

    await solve_rush(client, trio["mate"], 3)
    first = await post_run(client, score=3, mistakes=1, duration_s=170)
    assert first.status_code == 201
    assert first.json() | {"id": 0} == {"id": 0, "best": 3, "is_best": True}

    await solve_rush(client, trio["mate"], 2)
    worse = await post_run(client, score=2, filters={"theme": "mate_in_n", "phase": "opening"})
    assert worse.json() | {"id": 0} == {"id": 0, "best": 3, "is_best": False}

    await solve_rush(client, trio["mate"], 4)
    better = await post_run(client, score=4)
    assert better.json() | {"id": 0} == {"id": 0, "best": 4, "is_best": True}

    listing = (await client.get("/api/v1/puzzles/rush", params={"variant": "3min"})).json()
    assert listing["best"] == 4
    # Новые первыми, фильтры возвращаются без служебного варианта.
    assert [r["score"] for r in listing["recent"]] == [4, 2, 3]
    assert listing["recent"][1]["filters"] == {
        "theme": "mate_in_n",
        "phase": "opening",
        "eco": None,
    }
    assert listing["recent"][0]["filters"] == {"theme": None, "phase": None, "eco": None}
    assert (listing["recent"][2]["mistakes"], listing["recent"][2]["duration_s"]) == (1, 170)
    # Другой вариант — свой рекорд.
    other = (await client.get("/api/v1/puzzles/rush", params={"variant": "5min"})).json()
    assert other == {"best": None, "recent": []}


async def test_rush_recent_is_limited_to_ten(
    client: AsyncClient, trio: dict[str, uuid.UUID]
) -> None:
    for _ in range(12):
        assert (await post_run(client, score=0)).status_code == 201

    listing = (await client.get("/api/v1/puzzles/rush", params={"variant": "3min"})).json()

    assert len(listing["recent"]) == 10
    assert listing["best"] == 0


async def test_zero_score_is_not_a_record(client: AsyncClient) -> None:
    response = await post_run(client, score=0)

    assert response.json() | {"id": 0} == {"id": 0, "best": 0, "is_best": False}


async def test_rush_score_must_match_attempts(
    client: AsyncClient, trio: dict[str, uuid.UUID]
) -> None:
    await solve_rush(client, trio["mate"], 2)
    # Неверная попытка и попытки в других режимах счёт не подтверждают.
    await attempt(client, trio["mate"], moves_uci=["a1a7"], mode="rush")
    await attempt(client, trio["mate"], moves_uci=["a1a8"], mode="practice")
    await attempt(client, trio["mate"], moves_uci=["a1a8"], mode="srs")

    too_much = await post_run(client, score=3)

    assert too_much.status_code == 422
    assert too_much.json()["code"] == "validation_error"
    assert (await post_run(client, score=2)).status_code == 201
    # Нет записи о неверном — нет и забега.
    listing = (await client.get("/api/v1/puzzles/rush", params={"variant": "3min"})).json()
    assert [r["score"] for r in listing["recent"]] == [2]


async def test_rush_attempts_are_not_counted_twice(
    client: AsyncClient, trio: dict[str, uuid.UUID]
) -> None:
    await solve_rush(client, trio["mate"], 2)
    assert (await post_run(client, score=2)).status_code == 201

    # Те же две попытки второй раз счёт не подтверждают.
    assert (await post_run(client, score=2)).status_code == 422
    assert (await post_run(client, score=0)).status_code == 201


async def test_rush_window_is_duration_plus_a_minute(
    client: AsyncClient, db: Database, trio: dict[str, uuid.UUID]
) -> None:
    await solve_rush(client, trio["mate"], 2)
    async with db.sessionmaker() as session:
        await session.execute(
            update(PuzzleAttempt).values(created_at=datetime.now(UTC) - timedelta(seconds=300))
        )
        await session.commit()

    # Забег на 100 с: окно 160 с, попытки 5 минут назад в него не входят.
    assert (await post_run(client, score=1, duration_s=100)).status_code == 422
    # Забег на выживание в 280 с: окно 340 с — входят.
    survival = await post_run(client, variant="survival", score=2, duration_s=280)
    assert survival.status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        {"variant": "10min"},
        {"score": -1},
        {"mistakes": 4},
        {"mistakes": -1},
        {"duration_s": -5},
        {"variant": "3min", "duration_s": 400},
        {"variant": "5min", "duration_s": 400},
        {"variant": "survival", "mistakes": 1},
        {"filters": {"phase": "midgame"}},
        {"filters": {"theme": "Fork"}},
        {"filters": {"variant": "5min"}},
        {"score": 1.5},
    ],
)
async def test_rush_run_validation(client: AsyncClient, body: dict[str, Any]) -> None:
    response = await post_run(client, **body)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "validation_error"


async def test_rush_listing_requires_a_variant(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/puzzles/rush")).status_code == 422
    assert (await client.get("/api/v1/puzzles/rush", params={"variant": "1min"})).status_code == 422


@pytest.fixture
async def stranger(db: Database, settings: Settings) -> AsyncIterator[AsyncClient]:
    async with db.sessionmaker() as session:
        user = User(email=f"stranger-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(user)
        await session.commit()
    async with api_client(settings, user.id) as other:
        yield other


async def test_users_are_isolated(
    client: AsyncClient, stranger: AsyncClient, trio: dict[str, uuid.UUID]
) -> None:
    await solve_rush(client, trio["mate"], 2)
    assert (await post_run(client, score=2)).status_code == 201

    for mode in ("srs", "practice", "rush"):
        data = await next_puzzle(stranger, mode=mode)
        assert data["puzzle"] is None
        assert data["counts"]["total"] == 0
    themes = (await stranger.get("/api/v1/puzzles/themes")).json()
    assert themes["themes"] == []
    assert themes["openings"] == []
    assert [p["total"] for p in themes["phases"]] == [0, 0, 0]
    # Чужой пазл не решить ни в одном режиме; попытки чужого не засчитываются.
    for mode in ("srs", "practice", "rush"):
        response = await stranger.post(
            f"/api/v1/puzzles/{trio['mate']}/attempt", json={"moves_uci": ["a1a8"], "mode": mode}
        )
        assert response.status_code == 404
    # Свой счёт чужими попытками не подтвердить, а чужой рекорд и забеги не видны.
    assert (await post_run(stranger, score=1)).status_code == 422
    assert await solve_rush_foreign_check(client, stranger)


async def solve_rush_foreign_check(client: AsyncClient, stranger: AsyncClient) -> bool:
    theirs = (await stranger.get("/api/v1/puzzles/rush", params={"variant": "3min"})).json()
    mine = (await client.get("/api/v1/puzzles/rush", params={"variant": "3min"})).json()
    return theirs == {"best": None, "recent": []} and mine["best"] == 2
