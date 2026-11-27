"""Эталоны тренера: разбор архивов Chess.com, отбор выборки, сжатие разброса, квартили групп,
траектории, формат JSON. Сеть — фейковый транспорт httpx."""

import json
import uuid
from datetime import date
from typing import Any

import httpx
import pytest

from app.coach.metrics import GameAgg, spec_for
from app.coach.norms import TARGETS, nearest_center
from app.coach.norms.build import (
    MIN_BAND_PLAYERS,
    MIN_MULTI_PLAYERS,
    MonthPoint,
    SampleGame,
    build_bands,
    kaplan_meier,
    observed_points,
    shrunk_values,
    trajectory_rows,
    trajectory_starts,
    unit_variance,
)
from app.coach.norms.crawl import (
    Deficits,
    Fetcher,
    PlayerGoneError,
    completed_months,
    opponents,
    parse_archives,
    parse_month,
    pick_samples,
    summarize,
    trajectory_months,
)
from app.coach.norms.db import NORMS_DB, norms_url
from app.coach.norms_data import parse_norms, parse_trajectories
from app.core.config import Settings
from app.importers.http import RetryPolicy


def test_nearest_center() -> None:
    assert nearest_center(1500) == 1500
    assert nearest_center(1549) == 1500
    assert nearest_center(1550) == 1600
    assert nearest_center(749) is None
    assert nearest_center(750) == 800
    assert nearest_center(2649) == 2600
    assert nearest_center(2650) is None


def test_norms_url_refuses_other_databases(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(database_url="postgresql+asyncpg://u:p@h:5432/chess_review")
    monkeypatch.delenv("NORMS_DATABASE_URL", raising=False)
    assert norms_url(settings).endswith(f"/{NORMS_DB}")
    monkeypatch.setenv("NORMS_DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/chess_review")
    with pytest.raises(SystemExit):
        norms_url(settings)


# --- Архивы -----------------------------------------------------------------------------------


def _row(
    n: int,
    *,
    me: str = "Alice",
    color: str = "white",
    rating: int = 1500,
    opp: str = "Bob",
    opp_rating: int = 1520,
    tc: str = "600",
    rated: bool = True,
    rules: str = "chess",
) -> dict[str, Any]:
    mine = {"username": me, "rating": rating}
    theirs = {"username": opp, "rating": opp_rating}
    return {
        "url": f"https://www.chess.com/game/live/{1000 + n}",
        "time_control": tc,
        "rated": rated,
        "rules": rules,
        "end_time": 1_700_000_000 + n,
        "white": mine if color == "white" else theirs,
        "black": theirs if color == "white" else mine,
        "pgn": "",
    }


def test_parse_month_orients_by_player_and_skips_variants() -> None:
    rows = [
        _row(1),
        _row(2, color="black", rating=1490),
        _row(3, rules="chess960"),
        _row(4, me="Carol"),
        {"url": "bad"},
    ]
    games = parse_month(rows, "alice")
    assert [g.external_id for g in games] == ["live/1002", "live/1001"]
    assert games[0].rating == 1490
    assert games[0].time_class == "rapid"
    assert games[1].opponent == "bob"


def test_parse_archives_newest_first() -> None:
    data = {
        "archives": [
            "https://api.chess.com/pub/player/a/games/2025/01",
            "https://api.chess.com/pub/player/a/games/2026/10",
            "junk",
        ]
    }
    assert parse_archives(data) == [date(2026, 10, 1), date(2025, 1, 1)]


def test_summarize_rated_games_by_time_class() -> None:
    games = parse_month(
        [
            _row(1, rating=1500),
            _row(2, rating=1530),
            _row(3, tc="180", rating=1300),
            _row(4, rated=False, rating=2000),
        ],
        "alice",
    )
    by_tc = {s.time_class: s for s in summarize(games)}
    assert (by_tc["rapid"].games, by_tc["rapid"].first_rating, by_tc["rapid"].last_rating) == (
        2,
        1500,
        1530,
    )
    assert by_tc["blitz"].games == 1


def test_pick_samples_respects_need_limit_and_exclusions() -> None:
    games = parse_month(
        [_row(i, rating=1500) for i in range(8)]
        + [_row(20 + i, tc="180", rating=1800) for i in range(3)]
        + [_row(40, rated=False)],
        "alice",
    )
    needed = {("rapid", 1500): 3, ("blitz", 1800): 0}
    picked = pick_samples(games, needed, {}, exclude={"live/1007"}, per_player=5)
    assert len(picked) == 5
    assert all(g.time_class == "rapid" for g in picked)
    assert "live/1007" not in {g.external_id for g in picked}
    again = pick_samples(games, needed, {"rapid": 4}, exclude=set(), per_player=5)
    assert len(again) == 1


def test_opponents_hints_and_limit() -> None:
    games = parse_month(
        [_row(i, opp=f"p{i}", opp_rating=1400 + i) for i in range(10)]
        + [_row(50, opp="p1", opp_rating=1999, tc="180")],
        "alice",
    )
    hints = opponents(games, 100, "alice")
    assert hints["p1"] == {"rapid": 1401, "blitz": 1999}
    limited = opponents(games, 3, "alice")
    assert len(limited) == 3
    assert limited == opponents(games, 3, "alice")


def test_deficits_rank_priority_bands_first() -> None:
    d = Deficits(TARGETS)
    full = TARGETS.players
    d.players[("rapid", 1700)] = full
    d.games[("rapid", 1700)] = full * TARGETS.games_per_player
    assert d.need("rapid", 1700) == 0
    assert d.need("rapid", 1600) == full
    ranked = d.ranked()
    assert ranked[0][1] in range(1500, 2201)
    assert ("rapid", 1700) not in ranked
    # Игроков хватает, а партий мало — нужно ещё.
    d.players[("blitz", 1500)] = full
    d.games[("blitz", 1500)] = full * TARGETS.games_per_player - 6
    assert d.need("blitz", 1500) == 2


def test_completed_and_trajectory_months() -> None:
    archives = [date(2026, 11, 1), date(2026, 10, 1), date(2026, 9, 1), date(2026, 7, 1)]
    archives += [date(2023, 6, 1)]
    today = date(2026, 11, 27)
    assert completed_months(archives, today)[0] == date(2026, 10, 1)
    months = trajectory_months(archives, today, TARGETS)
    # Через 3 месяца от октября: октябрь, июль; 2023-06 — старше 3 лет.
    assert months == [date(2026, 10, 1), date(2026, 7, 1)]


async def test_fetcher_throttles_and_maps_gone() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "gone" in request.url.path:
            return httpx.Response(410)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"archives": []})

    slept: list[float] = []

    async def sleep(s: float) -> None:
        slept.append(s)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        fetcher = Fetcher(
            http, base_url="https://x", policy=RetryPolicy(sleep=sleep), min_interval_s=0.01
        )
        assert await fetcher.archives("a") == []
        with pytest.raises(PlayerGoneError):
            await fetcher.archives("gone")
    # 429 повторён после паузы из Retry-After (0 → ждём `rate_limit_wait_s`).
    assert calls[:2] == ["/pub/player/a/games/archives"] * 2
    assert slept == [RetryPolicy().rate_limit_wait_s]


# --- Квартили ---------------------------------------------------------------------------------


def test_shrinkage_narrows_noisy_players_only() -> None:
    # По одной партии на игрока: шум долей — биномиальный, разброс в основном шум.
    noisy = [[(1.0, 10.0)], [(3.0, 10.0)], [(2.0, 10.0)], [(0.0, 10.0)], [(4.0, 10.0)]]
    raw = [c / m * 100 for p in noisy for c, m in p]
    shrunk = shrunk_values(noisy, 100.0, proportion=True)
    assert max(shrunk) - min(shrunk) < 0.6 * (max(raw) - min(raw))
    assert sum(shrunk) / len(shrunk) == pytest.approx(sum(raw) / len(raw))
    # Не доля и одна партия — шум оценить не по чему, без сжатия.
    assert shrunk_values(noisy, 100.0) == pytest.approx(raw)
    # Много партий у каждого и реальные различия — почти без сжатия.
    solid = [[(k, 100.0)] * 20 for k in (1.0, 5.0, 9.0, 13.0, 17.0)]
    values = shrunk_values(solid, 100.0, proportion=True)
    assert values[-1] - values[0] == pytest.approx(16.0, rel=0.05)


def test_unit_variance_from_players_with_several_games() -> None:
    players = [[(70.0, 1.0), (80.0, 1.0)] for _ in range(MIN_MULTI_PLAYERS)]
    # Внутри игрока: (70 − 75)² + (80 − 75)² = 50, × k/(k − 1) = 2 → 100 на 2 партии.
    assert unit_variance(players, 75.0, proportion=False) == pytest.approx(50.0)
    assert unit_variance(players[:2], 0.2, proportion=True) == pytest.approx(0.16)


def _agg(**kwargs: Any) -> GameAgg:
    return GameAgg(game_id=uuid.uuid4(), **kwargs)


def test_build_bands_overlap_and_minimums() -> None:
    spec = spec_for("blunders_per_100")
    assert spec is not None
    games = [
        SampleGame(player=f"p{i}", rating=1450 + 5 * i, agg=_agg(moves=40, blunders=i % 4))
        for i in range(MIN_BAND_PLAYERS + 5)
        for _ in range(2)
    ]
    bands = {b["center"]: b for b in build_bands(games, [spec])}
    assert 1500 in bands
    band = bands[1500]
    assert band["players"] >= MIN_BAND_PLAYERS
    assert band["games"] == 2 * band["players"]
    q = band["metrics"]["blunders_per_100"]
    assert q["p25"] <= q["p50"] <= q["p75"]
    assert q["n"] == band["moves"]
    # Рейтинги 1450–1545: в группу 1700 (1600–1800) не попадает никто.
    assert 1700 not in bands


# --- Траектории -------------------------------------------------------------------------------


def _months(ratings: list[int | None], start: date = date(2024, 1, 1)) -> list[MonthPoint]:
    points = []
    y, m = start.year, start.month
    for r in ratings:
        points.append(MonthPoint(date(y, m, 1), 0 if r is None else 10, r, r))
        y, m = y + m // 12, m % 12 + 1
    return points


def test_trajectory_starts_reach_and_censoring() -> None:
    points = _months([1500, 1550, None, 1620, 1700, 1720])
    starts = trajectory_starts(points)
    first = next(s for s in starts if s.center == 1500)
    assert first.rating == 1500
    assert first.reached[100] is not None
    assert first.reached[200] is not None
    assert first.reached[300] is None
    assert first.observed_weeks > first.reached[200]  # type: ignore[operator]
    # Месяц без партий тоже наблюдён: активность — среднее с нулём.
    assert first.games_per_week == pytest.approx(10 * 5 / 6 / (365.25 / 12 / 7))
    # Второй старт — при первом попадании в группу 1600.
    assert {s.center for s in starts} == {1500, 1600, 1700}


def test_kaplan_meier_with_censoring() -> None:
    events = [(10.0, True), (20.0, False), (30.0, True), (40.0, False)]
    # t=10: 1/4 → S = 0.75; t=30: под риском 2, событие 1 → S = 0.375.
    assert kaplan_meier(events, 52) == pytest.approx(0.625)
    assert kaplan_meier(events, 15) == pytest.approx(0.25)
    assert kaplan_meier([], 52) == 0.0


def test_observed_points_fill_inactive_months() -> None:
    months = {date(2026, 7, 1): (10, 1500, 1510), date(2026, 10, 1): (5, 1520, 1530)}
    fetched = [date(2026, 7, 1), date(2026, 10, 1)]
    archives = [date(2026, 10, 1), date(2026, 9, 1), date(2026, 7, 1)]
    points = observed_points(months, fetched, archives, date(2026, 11, 27))
    # Август — нет архива, значит 0 партий; сентябрь — архив есть, но не загружен.
    assert [p.month.month for p in points] == [7, 8, 10]
    assert points[1].games == 0


def test_trajectory_rows_format_parses() -> None:
    starts = []
    for i in range(12):
        starts += trajectory_starts(_months([1500, 1550 + 10 * i, 1600 + 20 * i, 1700 + 30 * i]))
    rows = trajectory_rows(starts)
    row = next(r for r in rows if r["from_center"] == 1500 and r["gain"] == 100)
    assert row["players"] == 12
    assert 0 <= row["reached_52w"] <= row["reached_104w"] <= row["reached_156w"] <= 1
    raw = {"version": "t", "source": "chesscom", "built_at": None,
           "time_classes": {"rapid": {"rows": rows}}}  # fmt: skip
    parsed = parse_trajectories(json.loads(json.dumps(raw)))
    assert parsed.nearest("rapid", 1500, 100) is not None


def test_committed_data_files_parse_and_have_no_names() -> None:
    from app.coach.norms_data import DATA_DIR  # noqa: PLC0415

    norms_raw = (DATA_DIR / "norms.json").read_text()
    traj_raw = (DATA_DIR / "trajectories.json").read_text()
    parse_norms(json.loads(norms_raw))
    parse_trajectories(json.loads(traj_raw))
    for raw in (norms_raw, traj_raw):
        assert "username" not in raw
        assert "[Event" not in raw
