"""Диагностика тренера: перцентиль, интерполяция эталона, пороги слабых и сильных сторон
(чистая логика) и `GET /coach/diagnosis` на фикстурных партиях с фейковым эталоном."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.coach import diagnosis
from app.coach.diagnosis import (
    THRESHOLDS,
    MetricEval,
    Norm,
    evaluate_metric,
    find_gaps,
    norm_at,
    percentile,
    train_for,
)
from app.coach.metrics import GameAgg, MetricValue, motif_spec, spec_for
from app.coach.norms_data import Band, Norms, Quartiles
from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, CoachGoal, Color, Game, GameSource, Move
from app.db.session import Database
from app.review.types import MoveClass, Phase
from tests.conftest import api_client


def _spec(key: str) -> Any:
    spec = spec_for(key)
    assert spec is not None
    return spec


def _value(value: float, *, n: int = 1000, se: float | None = 0.1, events: float = 1e4) -> Any:
    return MetricValue(value=value, n=n, games=40, se=se, events=events)


NORM = Norm(p25=40.0, p50=50.0, p75=60.0)


# --- Перцентиль и эталон ----------------------------------------------------------------------


def test_percentile_piecewise_linear_inside_quartiles() -> None:
    assert percentile(50.0, NORM, higher_better=True) == pytest.approx(50.0)
    assert percentile(45.0, NORM, higher_better=True) == pytest.approx(37.5)
    assert percentile(60.0, NORM, higher_better=True) == pytest.approx(75.0)
    assert percentile(45.0, NORM, higher_better=False) == pytest.approx(62.5)


def test_percentile_tails_are_normal_and_continuous() -> None:
    assert percentile(40.0, NORM, higher_better=True) == pytest.approx(25.0)
    assert percentile(39.999, NORM, higher_better=True) == pytest.approx(25.0, abs=0.01)
    # p50 − 2σ: σ = 10 / 0.6745 → ≈ 2.3-й перцентиль.
    low = 50 - 2 * 10 / 0.6745
    assert percentile(low, NORM, higher_better=True) == pytest.approx(2.28, abs=0.05)
    assert percentile(1000.0, NORM, higher_better=True) == pytest.approx(100.0)


def test_percentile_degenerate_norm() -> None:
    flat = Norm(0.0, 0.0, 0.0)
    assert percentile(0.0, flat, higher_better=False) == pytest.approx(50.0, abs=50)
    assert percentile(1.0, flat, higher_better=False) == 0.0


def _band(center: int, **metrics: tuple[float, float, float]) -> Band:
    return Band(
        center=center,
        lo=center - 100,
        hi=center + 100,
        players=40,
        games=200,
        moves=8000,
        metrics={k: Quartiles(*v, n=40) for k, v in metrics.items()},
    )


def test_norm_at_interpolates_between_centers_and_clamps_edges() -> None:
    bands = [_band(1700, accuracy=(70, 75, 80)), _band(1800, accuracy=(72, 77, 82))]
    mid = norm_at(bands, "accuracy", 1730)
    assert mid is not None
    assert mid.p50 == pytest.approx(75.6)
    assert norm_at(bands, "accuracy", 1700) == Norm(70, 75, 80)
    # За краем — крайняя группа в пределах её ширины, дальше — нет эталона.
    assert norm_at(bands, "accuracy", 1880) == Norm(72, 77, 82)
    assert norm_at(bands, "accuracy", 2000) is None
    assert norm_at(bands, "conversion", 1750) is None


# --- Пороги -----------------------------------------------------------------------------------


def test_weakness_needs_low_target_percentile_and_stability() -> None:
    spec = _spec("blunders_per_100")
    target = Norm(2.0, 3.0, 4.0)
    weak = evaluate_metric(spec, _value(6.0, se=0.3), Norm(3.0, 4.0, 5.0), target)
    assert weak.status == "weakness"
    assert weak.severity == "high"
    assert weak.percentile is not None
    assert weak.percentile < 10
    # То же значение, но шумное (большая ошибка): не слабость.
    noisy = evaluate_metric(spec, _value(4.6, se=3.0), None, target)
    assert noisy.status == "neutral"


def test_weakness_severity_grades() -> None:
    spec = _spec("accuracy")
    target = Norm(70.0, 75.0, 80.0)
    medium = evaluate_metric(spec, _value(66.5, n=40, se=0.5), None, target)
    low = evaluate_metric(spec, _value(70.5, n=40, se=0.5), None, target)
    assert medium.status == low.status == "weakness"
    assert medium.severity == "medium"
    assert low.severity == "low"
    assert medium.score > low.score


def test_strength_is_against_current_group() -> None:
    spec = _spec("accuracy")
    current, target = Norm(60.0, 65.0, 70.0), Norm(70.0, 75.0, 80.0)
    e = evaluate_metric(spec, _value(74.0, n=40, se=0.5), current, target)
    assert e.status == "strength"
    assert e.current_percentile is not None
    assert e.current_percentile > 65
    assert e.percentile is not None
    assert e.percentile < 50


def test_insufficient_volume_and_missing_norms() -> None:
    spec = _spec("conversion")
    few = evaluate_metric(spec, _value(10.0, n=3), NORM, NORM)
    assert few.status == "insufficient"
    no_norms = evaluate_metric(spec, _value(10.0, n=30), None, None)
    assert no_norms.status == "insufficient"
    assert evaluate_metric(spec, None, NORM, NORM).status == "insufficient"


def test_motif_weakness_needs_enough_misses() -> None:
    spec = motif_spec("fork")
    target = Norm(0.2, 0.4, 0.6)
    rare = evaluate_metric(spec, _value(2.0, n=500, se=0.1, events=2), None, target)
    assert rare.status == "neutral"
    many = evaluate_metric(spec, _value(2.0, n=500, se=0.1, events=10), None, target)
    assert many.status == "weakness"


def _eval(key: str, status: str, score: float, severity: Any = "low") -> MetricEval:
    spec = motif_spec(key.removeprefix("motif:")) if key.startswith("motif:") else _spec(key)
    return MetricEval(spec, _value(1.0), None, None, 10.0, 80.0, status, severity, score)  # type: ignore[arg-type]


def test_find_gaps_orders_and_limits() -> None:
    evals = [
        _eval("motif:fork", "weakness", 80, "high"),
        _eval("motif:pin", "weakness", 70, "high"),
        _eval("motif:skewer", "weakness", 60, "high"),
        _eval("motif:overload", "weakness", 90, "medium"),
        _eval("accuracy", "weakness", 40, "medium"),
        _eval("conversion", "strength", 30),
        _eval("resilience", "strength", 60),
    ]
    strong, weak = find_gaps(evals)
    assert [e.spec.key for e in strong] == ["resilience", "conversion"]
    keys = [e.spec.key for e in weak]
    assert keys[:3] == ["motif:fork", "motif:pin", "motif:skewer"]
    assert "motif:overload" not in keys  # больше трёх мотивов не показываем
    assert "accuracy" in keys


def test_band_far_when_only_distant_groups() -> None:
    bands = [_band(1500), _band(2200)]
    assert not diagnosis.band_far(bands, 1600)
    assert diagnosis.band_far(bands, 1200)
    assert diagnosis.band_far([], 1700)


def test_train_mapping_like_insights() -> None:
    fork = train_for("motif:fork")
    assert fork is not None
    assert (fork.kind, fork.theme) == ("puzzles", "fork")
    endgame = train_for("accuracy_endgame")
    assert endgame is not None
    assert endgame.kind == "endgames"
    middle = train_for("accuracy_middlegame")
    assert middle is not None
    assert middle.phase == Phase.MIDDLEGAME
    conv = train_for("conversion")
    assert conv is not None
    assert conv.kind == "endgames"
    assert THRESHOLDS.min_games == 20


def test_evaluate_all_insufficient_below_min_games() -> None:
    games = [GameAgg(game_id=uuid.uuid4(), moves=40, accuracy=80.0) for _ in range(5)]
    bands = [_band(1500, accuracy=(70, 75, 80))]
    evals = diagnosis.evaluate_all(games, bands, 1500, 1700)
    assert {e.status for e in evals} == {"insufficient"}
    acc = next(e for e in evals if e.spec.key == "accuracy")
    assert diagnosis.metric_out(acc).value is None


# --- API --------------------------------------------------------------------------------------

FEN_W = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 {n}"
FEN_B = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 2 {n}"


def _move(ply: int, cls: MoveClass, *, best: str = "e2e4", missed: Sequence[str] = ()) -> Move:
    return Move(
        ply=ply,
        san=f"m{ply}",
        uci="e2e4",
        best_uci=best,
        best_san=f"b{ply}",
        fen_before=(FEN_W if ply % 2 else FEN_B).format(n=(ply + 1) // 2),
        win_before=50.0,
        win_after=50.0 if cls != MoveClass.BLUNDER else 20.0,
        accuracy=60.0 if cls == MoveClass.BLUNDER else 90.0,
        move_class=cls,
        motifs={"played": [], "missed": [{"type": m} for m in missed], "refutation": []},
        phase=Phase.MIDDLEGAME,
    )


async def _seed(db: Database, user_id: uuid.UUID, games: int) -> None:
    """`games` разобранных партий рапида белыми (рейтинг 1700): по 30 своих ходов, из них 3
    зевка с упущенной вилкой — 10 зевков на 100 ходов, норма группы — 2–4."""
    async with db.sessionmaker() as session:
        for i in range(games):
            g = Game(
                user_id=user_id,
                source=GameSource.CHESSCOM,
                external_id=f"{user_id}-{i}",
                pgn="*",
                white="me",
                black=f"opp{i}",
                white_elo=1700,
                black_elo=1700,
                result="1-0" if i % 2 else "0-1",
                time_control="600",
                played_at=datetime(2026, 1, 1 + i % 28, tzinfo=UTC),
                user_color=Color.WHITE,
            )
            session.add(g)
            await session.flush()
            moves = []
            for k in range(30):
                ply = 2 * k + 1
                if k in (5, 15, 25):
                    moves.append(_move(ply, MoveClass.BLUNDER, best="d2d4", missed=["fork"]))
                else:
                    moves.append(_move(ply, MoveClass.BEST))
            session.add(
                Analysis(
                    game_id=g.id,
                    depth=10,
                    status=AnalysisStatus.DONE,
                    white_accuracy=80.0 + i % 5,
                    black_accuracy=70.0,
                    moves=moves,
                )
            )
        session.add(
            CoachGoal(
                user_id=user_id,
                source=GameSource.CHESSCOM,
                time_class="rapid",
                start_rating=1650,
                target_rating=2000,
                minutes_per_day=45,
                days_per_week=5,
                tz="Europe/Moscow",
            )
        )
        await session.commit()


def _fake_norms() -> Norms:
    metrics = {
        "blunders_per_100": (2.0, 3.0, 4.0),
        "accuracy": (60.0, 65.0, 70.0),
        "motif:fork": (0.2, 0.4, 0.6),
    }
    bands = tuple(_band(c, **metrics) for c in (1700, 1800, 1900, 2000))
    return Norms(version="test", bands={"rapid": bands})


async def _new_user(db: Database) -> uuid.UUID:
    from app.db.models import User  # noqa: PLC0415

    async with db.sessionmaker() as session:
        user = User(email=f"{uuid.uuid4()}@example.test")
        session.add(user)
        await session.commit()
        return user.id


@pytest.mark.integration
async def test_diagnosis_without_goal_is_404(settings: Settings, db: Database) -> None:
    user_id = await _new_user(db)
    async with api_client(settings, user_id) as client:
        response = await client.get("/api/v1/coach/diagnosis")
    assert response.status_code == 404
    assert response.json()["code"] == "coach_goal_not_found"


@pytest.mark.integration
async def test_diagnosis_on_fixture_games(
    settings: Settings, db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(diagnosis, "load_norms", _fake_norms)
    user_id = await _new_user(db)
    await _seed(db, user_id, games=24)
    client: AsyncClient
    async with api_client(settings, user_id) as client:
        response = await client.get("/api/v1/coach/diagnosis")
    assert response.status_code == 200
    body = response.json()
    assert body["analyzed_games"] == 24
    assert body["current_rating"] == 1700
    assert (body["current_band"], body["target_band"]) == (1700, 2000)
    assert (body["current_band_far"], body["target_band_far"]) == (False, False)
    assert body["norms_version"] == "test"
    metrics = {(m["kind"], m["key"]): m for m in body["metrics"]}
    blunders = metrics[("metric", "blunders_per_100")]
    assert blunders["value"] == pytest.approx(10.0)
    assert blunders["status"] == "weakness"
    assert blunders["target"] == {"p25": 2.0, "p50": 3.0, "p75": 4.0}
    # Точность 80–84 против 60–70 текущей группы — сильная сторона.
    assert metrics[("metric", "accuracy")]["status"] == "strength"
    weak = {(g["kind"], g["key"]): g for g in body["weaknesses"]}
    assert ("motif", "fork") in weak
    fork = weak[("motif", "fork")]
    assert fork["lesson"] == "fork"
    assert fork["train"]["kind"] == "puzzles"
    assert fork["train"]["query"]["theme"] == "fork"
    assert 0 < len(fork["examples"]) <= 5
    assert weak[("metric", "blunders_per_100")]["lesson"] == "blunder_check"
    assert [g["key"] for g in body["strengths"]] == ["accuracy"]


@pytest.mark.integration
async def test_diagnosis_insufficient_with_few_games(
    settings: Settings, db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(diagnosis, "load_norms", _fake_norms)
    user_id = await _new_user(db)
    await _seed(db, user_id, games=5)
    async with api_client(settings, user_id) as client:
        body = (await client.get("/api/v1/coach/diagnosis")).json()
    assert body["analyzed_games"] == 5
    assert body["strengths"] == body["weaknesses"] == []
    assert {m["status"] for m in body["metrics"]} == {"insufficient"}
    assert all(m["value"] is None for m in body["metrics"])


def test_every_lesson_has_ru_and_en_text() -> None:
    from pathlib import Path  # noqa: PLC0415

    from app.coach.lessons import LESSONS  # noqa: PLC0415

    root = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "coach-lessons"
    for lang in ("ru", "en"):
        text = (root / f"{lang}.ts").read_text()
        missing = [
            key
            for key in LESSONS
            if f"  {key}: lesson(" not in text and f"  {key}: book(" not in text
        ]
        assert missing == [], lang
