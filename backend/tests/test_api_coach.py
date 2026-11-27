"""API тренера 17.2: цель, план, задания с автозачётом, отчёт, прогноз, уроки.

Диагностика 17.1 подменяется фейком (`app.coach.diagnosis.diagnose`), время — фиксированным
«сейчас» (`app.coach.tasks.now_utc`): среда 2026-11-25, 10:00 UTC, зона цели — Москва.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.schemas_coach import DiagnosisOut, GapOut
from app.api.schemas_insights import TrainOut, TrainQueryOut
from app.coach import diagnosis, tasks
from app.coach.goal import goal_out
from app.core.config import Settings
from app.db.models import (
    Analysis,
    AnalysisStatus,
    CoachGoal,
    Color,
    EndgameAttempt,
    Game,
    GameSource,
    Move,
    Puzzle,
    PuzzleAttempt,
    PuzzleRushRun,
    User,
)
from app.db.session import Database
from app.review.types import MoveClass, Phase
from tests.conftest import api_client

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
TODAY = date(2026, 11, 25)
MONDAY = date(2026, 11, 23)
TZ = "Europe/Moscow"
FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"


@dataclass
class Clock:
    now: datetime = NOW


def weak(key: str, score: float, **train: Any) -> GapOut:
    return GapOut(
        kind="motif",
        key=key,
        severity="high",
        score=score,
        value=10.0,
        target_p50=5.0,
        train=TrainOut(
            kind=train.pop("kind", "puzzles"),
            query=TrainQueryOut(**train),
            available=5,
        ),
        lesson=key,
        examples=[],
    )


@pytest.fixture
def weaknesses() -> list[GapOut]:
    return [weak("fork", 80, theme="fork")]


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    c = Clock()
    monkeypatch.setattr(tasks, "now_utc", lambda: c.now)
    return c


@pytest.fixture
def fake_diagnosis(monkeypatch: pytest.MonkeyPatch, weaknesses: list[GapOut]) -> list[int]:
    """Фейк 17.1: слабые стороны из фикстуры, метрика `accuracy` растёт с каждым вызовом."""
    calls: list[int] = []

    async def diagnose(session: Any, user_id: uuid.UUID, goal: CoachGoal) -> DiagnosisOut:
        calls.append(1)
        return DiagnosisOut.model_validate(
            {
                "goal": goal_out(goal, goal.start_rating).model_dump(),
                "current_rating": goal.start_rating,
                "current_band": 1700,
                "target_band": 2000,
                "norms_version": "placeholder",
                "analyzed_games": 30,
                "min_games": 20,
                "metrics": [
                    {
                        "kind": "metric",
                        "key": "accuracy",
                        "value": 70.0 + len(calls),
                        "n": 30,
                        "direction": "higher_better",
                        "current": None,
                        "target": None,
                        "percentile": None,
                        "status": "neutral",
                    }
                ],
                "strengths": [],
                "weaknesses": [w.model_dump() for w in weaknesses],
            }
        )

    monkeypatch.setattr(diagnosis, "diagnose", diagnose)
    return calls


@pytest.fixture
async def user(db: Database) -> uuid.UUID:
    async with db.sessionmaker() as session:
        u = User(email=f"coach-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(u)
        await session.commit()
        return u.id


@pytest.fixture
async def client(
    settings: Settings, user: uuid.UUID, clock: Clock, fake_diagnosis: list[int]
) -> AsyncIterator[AsyncClient]:
    async with api_client(settings, user) as c:
        yield c


def game(
    user_id: uuid.UUID,
    played_at: datetime | None,
    *,
    rating: int = 1700,
    source: GameSource = GameSource.CHESSCOM,
    time_control: str | None = "600",
    pgn: str = "*",
    name: str | None = None,
) -> Game:
    return Game(
        user_id=user_id,
        source=source,
        external_id=name or uuid.uuid4().hex,
        pgn=pgn,
        white="me",
        black="them",
        white_elo=rating,
        black_elo=1500,
        result="1-0",
        time_control=time_control,
        played_at=played_at,
        user_color=Color.WHITE,
    )


async def add(db: Database, *rows: Any) -> None:
    async with db.sessionmaker() as session:
        session.add_all(rows)
        await session.commit()


async def set_goal(client: AsyncClient, **kw: Any) -> dict[str, Any]:
    body = {
        "source": "chesscom",
        "time_class": "rapid",
        "target_rating": 2000,
        "minutes_per_day": 45,
        "days_per_week": 5,
        "tz": TZ,
    } | kw
    response = await client.put("/api/v1/coach/goal", json=body)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def seed_ratings(db: Database, user: uuid.UUID) -> None:
    await add(
        db,
        game(user, NOW - timedelta(days=30), rating=1650),
        game(user, NOW - timedelta(days=2), rating=1710),
        game(user, NOW - timedelta(days=3), rating=1300, time_control="180"),
        game(user, NOW - timedelta(days=1), rating=1500, source=GameSource.LICHESS),
        # PGN-партии рейтинга площадки не дают.
        game(user, NOW, rating=2500, source=GameSource.PGN),
    )


# --- Цель ------------------------------------------------------------------------------------


async def test_goal_lifecycle(client: AsyncClient, db: Database, user: uuid.UUID) -> None:
    empty = (await client.get("/api/v1/coach/goal")).json()
    assert empty == {"goal": None, "ratings": []}
    no_rating = await client.put(
        "/api/v1/coach/goal",
        json={
            "source": "chesscom",
            "time_class": "rapid",
            "target_rating": 2000,
            "minutes_per_day": 45,
            "days_per_week": 5,
            "tz": TZ,
        },
    )
    assert no_rating.status_code == 422
    assert no_rating.json()["code"] == "coach_no_rating"

    await seed_ratings(db, user)
    state = (await client.get("/api/v1/coach/goal")).json()
    ratings = {(r["source"], r["time_class"]): (r["rating"], r["games"]) for r in state["ratings"]}
    assert ratings == {
        ("chesscom", "rapid"): (1710, 2),
        ("chesscom", "blitz"): (1300, 1),
        ("lichess", "rapid"): (1500, 1),
    }

    low = await client.put(
        "/api/v1/coach/goal",
        json={
            "source": "chesscom",
            "time_class": "rapid",
            "target_rating": 1700,
            "minutes_per_day": 45,
            "days_per_week": 5,
            "tz": TZ,
        },
    )
    assert low.status_code == 422
    assert low.json()["code"] == "validation_error"
    bad_tz = await client.put(
        "/api/v1/coach/goal",
        json={
            "source": "chesscom",
            "time_class": "rapid",
            "target_rating": 2000,
            "minutes_per_day": 45,
            "days_per_week": 5,
            "tz": "Mars/Olympus",
        },
    )
    assert bad_tz.status_code == 422

    first = await set_goal(client)
    assert first["start_rating"] == first["current_rating"] == 1710
    assert first["achieved_at"] is None
    second = await set_goal(client, target_rating=1800)
    assert second["id"] != first["id"]
    async with db.sessionmaker() as session:
        goals = (await session.scalars(select(CoachGoal).where(CoachGoal.user_id == user))).all()
    assert len(goals) == 2
    assert sum(g.archived_at is None for g in goals) == 1

    # Рейтинг дорос до цели — `achieved_at`.
    await add(db, game(user, NOW - timedelta(hours=1), rating=1805))
    state = (await client.get("/api/v1/coach/goal")).json()
    assert state["goal"]["current_rating"] == 1805
    assert state["goal"]["achieved_at"] is not None

    assert (await client.delete("/api/v1/coach/goal")).status_code == 204
    assert (await client.get("/api/v1/coach/goal")).json()["goal"] is None
    missing = await client.get("/api/v1/coach/today")
    assert missing.status_code == 404
    assert missing.json()["code"] == "coach_goal_not_found"


# --- План и задания --------------------------------------------------------------------------


async def seed_puzzles(db: Database, user: uuid.UUID, n: int = 40) -> list[uuid.UUID]:
    puzzles = [
        Puzzle(
            user_id=user,
            fen=f"{FEN}#{i}",
            solution_uci=["d2d4"],
            themes=["fork"] if i % 2 == 0 else ["pin"],
        )
        for i in range(n)
    ]
    await add(db, *puzzles)
    return [p.id for p in puzzles]


async def test_plan_is_built_lazily_once_per_week(
    client: AsyncClient, db: Database, user: uuid.UUID, fake_diagnosis: list[int], clock: Clock
) -> None:
    await seed_ratings(db, user)
    await seed_puzzles(db, user)
    await set_goal(client)
    plan = (await client.get("/api/v1/coach/plan")).json()
    assert plan["week_start"] == MONDAY.isoformat()
    assert plan["next_rebuild"] == (MONDAY + timedelta(days=7)).isoformat()
    assert [d["day"] for d in plan["days"]] == [
        (MONDAY + timedelta(days=i)).isoformat() for i in range(7)
    ]
    # Собран с сегодня (среда): пн и вт — пустые, учебные — ср, пт, сб.
    study = [d["day"] for d in plan["days"] if not d["rest_day"]]
    assert study == ["2026-11-25", "2026-11-27", "2026-11-28"]
    assert [f["key"] for f in plan["focus"]] == ["fork"]
    kinds = {a["kind"] for a in plan["allocation"]}
    assert {"puzzles", "play", "review", "lesson"} <= kinds
    assert len(fake_diagnosis) == 1

    today = (await client.get("/api/v1/coach/today")).json()
    assert today["day"] == TODAY.isoformat()
    assert not today["rest_day"]
    assert today["streak_days"] == 0
    assert today["minutes_total"] == sum(t["minutes"] for t in today["tasks"])
    hrefs = {t["kind"]: t["href"] for t in today["tasks"]}
    assert hrefs["lesson"] == "/coach/lessons/fork"
    assert hrefs["play"] == "/play"
    play = next(t for t in today["tasks"] if t["kind"] == "play")
    assert play["params"] == {"bot_elo": 1700}
    # Повторное обращение план не пересобирает.
    assert len(fake_diagnosis) == 1

    # Пересборка моложе часа — тот же план.
    same = (await client.post("/api/v1/coach/plan/rebuild")).json()
    assert same["created_at"] == plan["created_at"]
    assert len(fake_diagnosis) == 1
    clock.now = NOW + timedelta(hours=2)
    rebuilt = (await client.post("/api/v1/coach/plan/rebuild")).json()
    assert rebuilt["created_at"] != plan["created_at"]
    assert len(fake_diagnosis) == 2

    # Новая неделя — новый план при первом обращении.
    clock.now = NOW + timedelta(days=7)
    nxt = (await client.get("/api/v1/coach/today")).json()
    assert nxt["day"] == "2026-12-02"
    assert len(fake_diagnosis) == 3


async def test_progress_is_counted_from_activity(
    client: AsyncClient, db: Database, user: uuid.UUID
) -> None:
    await seed_ratings(db, user)
    puzzle_ids = await seed_puzzles(db, user)
    await set_goal(client, minutes_per_day=90)
    today = (await client.get("/api/v1/coach/today")).json()
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for t in today["tasks"]:
        by_kind.setdefault(t["kind"], []).append(t)
    assert all(t["progress"] == 0 and not t["done"] for t in today["tasks"])

    # Пазлы сегодня по Москве (вчерашние и забеги не считаются), часть — с вилкой.
    attempts = [
        PuzzleAttempt(puzzle_id=pid, user_id=user, correct=True, mode="practice", created_at=NOW)
        for pid in puzzle_ids[:6]
    ]
    attempts.append(
        PuzzleAttempt(
            puzzle_id=puzzle_ids[0],
            user_id=user,
            correct=True,
            mode="practice",
            created_at=datetime(2026, 11, 24, 20, 30, tzinfo=UTC),  # 23:30 вчера по Москве
        )
    )
    attempts.append(
        PuzzleAttempt(
            puzzle_id=puzzle_ids[1], user_id=user, correct=True, mode="rush", created_at=NOW
        )
    )
    # 21:30 UTC 24-го — уже 00:30 25-го по Москве.
    attempts.append(
        PuzzleAttempt(
            puzzle_id=puzzle_ids[2],
            user_id=user,
            correct=False,
            mode="srs",
            created_at=datetime(2026, 11, 24, 21, 30, tzinfo=UTC),
        )
    )
    await add(db, *attempts)
    # Партия цели сегодня и партия с ботом из браузера (дата без времени — 00:00 UTC).
    await add(
        db,
        game(user, NOW - timedelta(hours=1), rating=1720),
        game(
            user,
            datetime(2026, 11, 25, tzinfo=UTC),
            source=GameSource.PGN,
            time_control=None,
            pgn='[Event "Партия с ботом"]\n[Site "Chess Review"]\n[Date "2026.11.25"]\n\n1. e4 *',
        ),
        # Блиц — не партия цели; бот вчера — не сегодня.
        game(user, NOW - timedelta(hours=1), time_control="180"),
        game(
            user,
            datetime(2026, 11, 24, tzinfo=UTC),
            source=GameSource.PGN,
            time_control=None,
            pgn='[Site "Chess Review"]\n[Date "2026.11.24"]\n\n1. e4 *',
        ),
    )
    today = (await client.get("/api/v1/coach/today")).json()
    tasks_by_kind: dict[str, list[dict[str, Any]]] = {}
    for t in today["tasks"]:
        tasks_by_kind.setdefault(t["kind"], []).append(t)
    general = next(t for t in tasks_by_kind["puzzles"] if "theme" not in t["params"])
    assert general["progress"] == 7
    assert general["href"] == "/puzzles?mode=practice"
    themed = [t for t in tasks_by_kind["puzzles"] if t["params"].get("theme") == "fork"]
    for t in themed:
        assert t["href"] == "/puzzles?mode=practice&theme=fork"
        # Вилка — чётные пазлы из первых шести и ночной (№ 2).
        assert t["progress"] == 4
    play = tasks_by_kind["play"][0]
    assert play["progress"] == 2
    assert play["done"] == (play["target"] <= 2)
    review = tasks_by_kind["review"][0]
    # Разбор — к последней партии дня.
    assert review["href"].startswith("/games/")
    assert review["progress"] == 0

    # Урок — прочитан, задание засчитано.
    lesson = tasks_by_kind["lesson"][0]
    read = await client.post(f"/api/v1/coach/lessons/{lesson['params']['lesson']}/read")
    assert read.json() == {"key": "fork", "kind": "motif", "read": True}
    # Разбор — вручную.
    done = await client.post(f"/api/v1/coach/tasks/{review['id']}/done")
    assert done.status_code == 200
    assert done.json()["done"]
    today = (await client.get("/api/v1/coach/today")).json()
    states = {t["id"]: t for t in today["tasks"]}
    assert states[lesson["id"]]["done"]
    assert states[review["id"]]["done"]
    assert today["minutes_done"] > 0


async def test_other_trainings_and_streak(
    client: AsyncClient,
    db: Database,
    user: uuid.UUID,
    weaknesses: list[GapOut],
    clock: Clock,
) -> None:
    weaknesses[:] = [
        weak("fork", 80, theme="fork"),
        weak("endgame", 60, kind="endgames"),
    ]
    weaknesses[1].key = "accuracy_endgame"
    weaknesses[1].kind = "metric"
    weaknesses[1].lesson = "endgame_technique"
    tt = weak("time_trouble_share", 40)
    tt.kind = "metric"
    tt.lesson = "time_management"
    weaknesses.append(tt)
    await seed_ratings(db, user)
    await seed_puzzles(db, user)
    clock.now = datetime(2026, 11, 23, 6, tzinfo=UTC)  # понедельник
    await set_goal(client, days_per_week=7, minutes_per_day=60)
    today = (await client.get("/api/v1/coach/today")).json()
    kinds = {t["kind"] for t in today["tasks"]}
    assert today["day"] == "2026-11-23"
    plan = (await client.get("/api/v1/coach/plan")).json()
    all_tasks = [t for d in plan["days"] for t in d["tasks"]]
    hrefs = {t["kind"]: t["href"] for t in all_tasks}
    assert hrefs["endgames"] == "/play/endgames?tab=mine"
    assert hrefs["rush"] == "/puzzles?mode=rush"
    assert kinds

    monday = clock.now
    await add(
        db,
        EndgameAttempt(
            user_id=user,
            source="game",
            key="1",
            goal="win",
            success=True,
            plies=10,
            created_at=monday,
        ),
        PuzzleRushRun(user_id=user, score=10, mistakes=1, duration_s=180, created_at=monday),
    )
    # Выполнить всё в понедельник: вручную то, что не засчиталось само.
    today = (await client.get("/api/v1/coach/today")).json()
    for t in today["tasks"]:
        if t["kind"] == "endgames":
            assert t["progress"] == 1
        if t["kind"] == "rush":
            assert t["progress"] == 1
        if not t["done"]:
            await client.post(f"/api/v1/coach/tasks/{t['id']}/done")
    assert (await client.get("/api/v1/coach/today")).json()["streak_days"] == 1
    # Вторник: вчера всё сделано, сегодня ещё нет.
    clock.now = monday + timedelta(days=1)
    tuesday = (await client.get("/api/v1/coach/today")).json()
    assert tuesday["streak_days"] == 1
    for t in tuesday["tasks"]:
        await client.post(f"/api/v1/coach/tasks/{t['id']}/done")
    # Четверг: среда пропущена — серия только из сегодняшнего (если выполнено) — 0.
    clock.now = monday + timedelta(days=3)
    assert (await client.get("/api/v1/coach/today")).json()["streak_days"] == 0


async def test_task_done_is_isolated(
    client: AsyncClient, db: Database, user: uuid.UUID, settings: Settings
) -> None:
    await seed_ratings(db, user)
    await set_goal(client)
    task = (await client.get("/api/v1/coach/today")).json()["tasks"][0]
    async with db.sessionmaker() as session:
        other = User(email=f"other-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(other)
        await session.commit()
    async with api_client(settings, other.id) as stranger:
        response = await stranger.post(f"/api/v1/coach/tasks/{task['id']}/done")
        assert response.status_code == 404
        assert response.json()["code"] == "coach_task_not_found"
    missing = await client.post("/api/v1/coach/tasks/999999999/done")
    assert missing.status_code == 404


# --- Отчёт и прогноз -------------------------------------------------------------------------


async def test_report_for_last_week(
    client: AsyncClient, db: Database, user: uuid.UUID, clock: Clock
) -> None:
    await seed_ratings(db, user)
    await set_goal(client)
    assert (await client.get("/api/v1/coach/report")).json() == {"report": None}
    week = (await client.get("/api/v1/coach/plan")).json()
    first = next(t for d in week["days"] for t in d["tasks"])
    await client.post(f"/api/v1/coach/tasks/{first['id']}/done")
    await add(
        db,
        game(user, datetime(2026, 11, 26, 12, tzinfo=UTC), rating=1730),
        game(user, datetime(2026, 11, 27, 12, tzinfo=UTC), rating=1750),
    )
    clock.now = NOW + timedelta(days=7)
    body = (await client.get("/api/v1/coach/report")).json()["report"]
    assert body["week_start"] == MONDAY.isoformat()
    # Отмечено вручную первое задание; партия пятницы засчитала пятничную партию задним числом.
    friday = next(
        t
        for d in week["days"]
        if d["day"] == "2026-11-27"
        for t in d["tasks"]
        if t["kind"] == "play"
    )
    assert body["tasks_done"] == 2
    assert body["tasks_total"] == sum(len(d["tasks"]) for d in week["days"])
    assert body["minutes_done"] == first["minutes"] + friday["minutes"]
    # Пн (из сида), чт и пт.
    assert body["games_played"] == 3
    assert body["rating_start"] == 1650
    assert body["rating_end"] == 1750
    accuracy = body["metrics"][0]
    assert accuracy["key"] == "accuracy"
    assert accuracy["before"] < accuracy["after"]


async def test_forecast_placeholder_is_honest(
    client: AsyncClient, db: Database, user: uuid.UUID
) -> None:
    await seed_ratings(db, user)
    await set_goal(client)
    fc = (await client.get("/api/v1/coach/forecast")).json()
    # Эталон — заглушка, партий мало: диапазона нет, уверенность низкая.
    assert fc["status"] == "insufficient"
    assert fc["confidence"] == "low"
    assert fc["weeks_p50"] is None
    assert fc["date_p80"] is None
    assert fc["start_rating"] == 1710
    assert fc["target_rating"] == 2000
    assert fc["basis"]["user_games"] == 2
    assert [p["rating"] for p in fc["history"]] == [1650, 1710]


async def test_forecast_by_own_trend(client: AsyncClient, db: Database, user: uuid.UUID) -> None:
    # 12 недель по 4 партии, +10 в неделю.
    games = [
        game(user, NOW - timedelta(weeks=12 - w, hours=h), rating=1600 + 10 * w)
        for w in range(12)
        for h in range(4)
    ]
    await add(db, *games)
    await set_goal(client, target_rating=1800)
    fc = (await client.get("/api/v1/coach/forecast")).json()
    assert fc["confidence"] == "low"
    assert fc["status"] == "on_track"
    assert fc["basis"]["weekly_trend"] == pytest.approx(10, abs=1)
    assert fc["weeks_p50"] is not None
    assert fc["weeks_p50"] <= fc["weeks_p80"]
    assert fc["projection"]


# --- Уроки -----------------------------------------------------------------------------------


async def test_lessons(client: AsyncClient, db: Database, user: uuid.UUID) -> None:
    g = game(user, NOW - timedelta(days=1))
    await add(db, g)
    move_fork = Move(
        ply=1,
        san="Nc3",
        uci="b1c3",
        best_uci="f3e5",
        best_san="Nxe5",
        fen_before=FEN,
        win_before=50.0,
        win_after=30.0,
        accuracy=40.0,
        move_class=MoveClass.MISTAKE,
        motifs={"played": [], "missed": [{"type": "fork"}], "refutation": [], "sacrifice": None},
        phase=Phase.OPENING,
    )
    await add(db, Analysis(game_id=g.id, depth=10, status=AnalysisStatus.DONE, moves=[move_fork]))
    listing = (await client.get("/api/v1/coach/lessons")).json()["lessons"]
    keys = {item["key"]: item for item in listing}
    assert keys["fork"] == {"key": "fork", "kind": "motif", "read": False}
    assert keys["blunder_check"]["kind"] == "skill"

    fork = (await client.get("/api/v1/coach/lessons/fork")).json()
    assert fork["kind"] == "motif"
    assert [e["ply"] for e in fork["examples"]] == [1]
    assert fork["train"]["kind"] == "puzzles"
    assert fork["train"]["query"]["theme"] == "fork"
    opening = (await client.get("/api/v1/coach/lessons/opening_principles")).json()
    assert [e["san"] for e in opening["examples"]] == ["Nc3"]
    endgame = (await client.get("/api/v1/coach/lessons/endgame_technique")).json()
    assert endgame["examples"] == []
    assert endgame["train"]["kind"] == "endgames"

    missing = await client.get("/api/v1/coach/lessons/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "lesson_not_found"
    assert (await client.post("/api/v1/coach/lessons/nope/read")).status_code == 404
    await client.post("/api/v1/coach/lessons/fork/read")
    again = (await client.get("/api/v1/coach/lessons/fork")).json()
    assert again["read"] is True
