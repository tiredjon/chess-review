"""Сбор выборки эталона с публичного API Chess.com (`python -m app.coach.norms crawl`).

Вежливо: один запрос за раз, между началами запросов не меньше `MIN_INTERVAL_S`, на 429 —
пауза из Retry-After (общий `get_with_retry`), User-Agent — общий, без личных данных.

Как набирается выборка:
1. Семена — соперники из партий Chess.com в рабочей БД (только чтение) с рейтингом из
   последней партии против них — подсказка, в какую группу игрок попадёт.
2. Каждый шаг выбирает группу (контроль × центр) с наибольшей нехваткой игроков (группы
   1500–2200 — в первую очередь) и игрока из очереди с подсказкой в эту группу.
3. У игрока берутся последние `sample_months` месяцев архива: до `games_per_player` рейтинговых
   партий каждого контроля (рапид, блиц), чья группа — по рейтингу игрока в момент партии —
   ещё не набрана; соперники из этих месяцев встают в очередь со своими подсказками.
4. Траектории: у уже отобранных игроков — архивы за `trajectory_months` месяцев через
   `trajectory_stride` (месяцы без партий видны по списку архивов и не запрашиваются).
Прогресс — в таблицах `norms_*`: прерванный сбор продолжается с того же места.
"""

import asyncio
import random
import re
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.coach.norms import (
    BAND_CENTERS,
    NORM_TIME_CLASSES,
    PRIORITY_BANDS,
    STAGES,
    TARGETS,
    SampleTargets,
    nearest_center,
)
from app.coach.norms.db import ensure_schema, service_user
from app.db.models import Color, Game, GameSource, User
from app.importers.http import RetryPolicy, get_with_retry
from app.importers.sources import SourceGame, convert
from app.importers.store import insert_games
from app.review.game_rating import TimeClass, time_class

log = structlog.get_logger(__name__)

SOURCE = "Chess.com"
MIN_INTERVAL_S = 1.1
# Без ников и контактов: только назначение запросов.
USER_AGENT = "ChessReview/0.1 (self-hosted game review; rating-group sample, 1 req/s)"
# Соперников из архива игрока в очередь — не больше (иначе очередь растёт на порядки).
MAX_NEW_OPPONENTS = 40
_ARCHIVE_RE = re.compile(r"/games/(\d{4})/(\d{2})/?$")
_GAME_URL_RE = re.compile(r"/game/(live|daily)/(\d+)")


class PlayerGoneError(Exception):
    """404 / 410: аккаунт удалён или закрыт."""


# --- HTTP ---------------------------------------------------------------------------------------


class Fetcher:
    """Последовательные GET к API с паузой между началами запросов."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str = "https://api.chess.com",
        policy: RetryPolicy | None = None,
        min_interval_s: float = MIN_INTERVAL_S,
    ) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.policy = policy or RetryPolicy(attempts=6, rate_limit_wait_s=60.0, backoff_s=5.0)
        self.min_interval_s = min_interval_s
        self._last = 0.0
        self.requests = 0

    async def json(self, path: str) -> dict[str, Any]:
        wait = self._last + self.min_interval_s - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last = time.monotonic()
        self.requests += 1
        response = await get_with_retry(
            self.http, f"{self.base_url}{path}", source=SOURCE, policy=self.policy
        )
        if response.status_code in (httpx.codes.NOT_FOUND, httpx.codes.GONE):
            raise PlayerGoneError(path)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def archives(self, username: str) -> list[date]:
        data = await self.json(f"/pub/player/{username}/games/archives")
        return parse_archives(data)

    async def month(self, username: str, month: date) -> list[dict[str, Any]]:
        data = await self.json(f"/pub/player/{username}/games/{month.year:04d}/{month.month:02d}")
        return [row for row in data.get("games", []) if isinstance(row, dict)]


def parse_archives(data: dict[str, Any]) -> list[date]:
    """Месяцы с партиями, новые первыми."""
    months = {
        date(int(m[1]), int(m[2]), 1)
        for url in data.get("archives", [])
        if isinstance(url, str) and (m := _ARCHIVE_RE.search(url))
    }
    return sorted(months, reverse=True)


# --- Разбор месяца (чистые функции) -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MonthGame:
    """Партия из архива с точки зрения игрока выборки."""

    external_id: str
    time_class: TimeClass
    rated: bool
    end_time: int
    color: Color
    rating: int
    opponent: str
    opponent_rating: int
    pgn: str


def _side(row: dict[str, Any], color: str) -> tuple[str, int] | None:
    side = row.get(color)
    if not isinstance(side, dict):
        return None
    name, rating = side.get("username"), side.get("rating")
    if not isinstance(name, str) or not isinstance(rating, int):
        return None
    return name.lower(), rating


def parse_month(rows: Iterable[dict[str, Any]], username: str) -> list[MonthGame]:
    """Классические партии игрока (рапид / блиц / буллет / daily), новые первыми."""
    games: list[MonthGame] = []
    for row in rows:
        if row.get("rules", "chess") != "chess":
            continue
        match = _GAME_URL_RE.search(str(row.get("url", "")))
        white, black = _side(row, "white"), _side(row, "black")
        if match is None or white is None or black is None:
            continue
        if white[0] == username:
            color, me, opp = Color.WHITE, white, black
        elif black[0] == username:
            color, me, opp = Color.BLACK, black, white
        else:
            continue
        games.append(
            MonthGame(
                external_id=f"{match[1]}/{match[2]}",
                time_class=time_class(str(row.get("time_control", "")) or None),
                rated=bool(row.get("rated", False)),
                end_time=int(row.get("end_time") or 0),
                color=color,
                rating=me[1],
                opponent=opp[0],
                opponent_rating=opp[1],
                pgn=str(row.get("pgn", "")),
            )
        )
    return sorted(games, key=lambda g: g.end_time, reverse=True)


@dataclass(frozen=True, slots=True)
class MonthSummary:
    time_class: str
    games: int
    first_rating: int
    last_rating: int


def summarize(games: Sequence[MonthGame]) -> list[MonthSummary]:
    """Рейтинговые партии месяца по контролю: число, рейтинг в первой и последней."""
    by_tc: dict[str, list[MonthGame]] = {}
    for g in games:
        if g.rated:
            by_tc.setdefault(g.time_class, []).append(g)
    result = []
    for tc, items in sorted(by_tc.items()):
        ordered = sorted(items, key=lambda g: g.end_time)
        result.append(MonthSummary(tc, len(ordered), ordered[0].rating, ordered[-1].rating))
    return result


def pick_samples(
    games: Sequence[MonthGame],
    needed: dict[tuple[str, int], int],
    taken: dict[str, int],
    *,
    exclude: set[str],
    per_player: int,
) -> list[MonthGame]:
    """Партии игрока в выборку: рейтинговые, рапид / блиц, группа (по рейтингу в момент партии)
    ещё не набрана, не больше `per_player` на контроль (с учётом уже взятых `taken`)."""
    picked: list[MonthGame] = []
    counts = Counter(taken)
    for g in games:
        if not g.rated or g.time_class not in NORM_TIME_CLASSES or g.external_id in exclude:
            continue
        center = nearest_center(g.rating)
        if center is None or needed.get((g.time_class, center), 0) <= 0:
            continue
        if counts[g.time_class] >= per_player:
            continue
        counts[g.time_class] += 1
        picked.append(g)
    return picked


def opponents(games: Sequence[MonthGame], limit: int, seed: str) -> dict[str, dict[str, int]]:
    """Соперники из рейтинговых партий рапида и блица → подсказки рейтинга по контролю
    (из последней партии). Если их больше `limit` — случайные (детерминированно по `seed`)."""
    hints: dict[str, dict[str, int]] = {}
    for g in games:  # новые первыми: первая встреча — свежий рейтинг
        if g.rated and g.time_class in NORM_TIME_CLASSES:
            hints.setdefault(g.opponent, {}).setdefault(g.time_class, g.opponent_rating)
    names = sorted(hints)
    if len(names) > limit:
        names = random.Random(seed).sample(names, limit)
    return {name: hints[name] for name in names}


# --- Нехватка по группам ----------------------------------------------------------------------


@dataclass(slots=True)
class Deficits:
    """Сколько ещё нужно игроков в «ближайшую» группу по контролю."""

    targets: SampleTargets
    players: dict[tuple[str, int], int] = field(default_factory=dict)
    games: dict[tuple[str, int], int] = field(default_factory=dict)

    def need(self, tc: str, center: int) -> int:
        """Нехватка в «игроках»: по игрокам и по партиям (партии / норма на игрока)."""
        t = self.targets
        by_players = t.players - self.players.get((tc, center), 0)
        need_games = t.players * t.games_per_player - self.games.get((tc, center), 0)
        by_games = -(-need_games // t.games_per_player)
        return max(0, by_players, by_games)

    def needed(self) -> dict[tuple[str, int], int]:
        """Нехватка по собираемым группам (`STAGES` × `PRIORITY_BANDS`); остальные — 0."""
        return {
            (tc, c): self.need(tc, c) if c in PRIORITY_BANDS else 0
            for tc in NORM_TIME_CLASSES
            for c in BAND_CENTERS
        }

    def ranked(self) -> list[tuple[str, int]]:
        """Группы с нехваткой: сначала контроль первого этапа (рапид), внутри — по нехватке."""
        keys = [k for k, v in self.needed().items() if v > 0]
        return sorted(keys, key=lambda k: (STAGES.index(k[0]), -self.need(*k), k[1]))


async def load_deficits(session: AsyncSession, targets: SampleTargets) -> Deficits:
    rows = await session.execute(
        text(
            "SELECT time_class, center, count(DISTINCT username) AS players, count(*) AS games "
            "FROM norms_samples GROUP BY time_class, center"
        )
    )
    d = Deficits(targets)
    for row in rows:
        d.players[(row.time_class, row.center)] = int(row.players)
        d.games[(row.time_class, row.center)] = int(row.games)
    return d


# --- Очередь игроков ----------------------------------------------------------------------------


async def enqueue(session: AsyncSession, hints: dict[str, dict[str, int]], depth: int) -> int:
    if not hints:
        return 0
    rows = [
        {"u": name, "r": h.get("rapid"), "b": h.get("blitz"), "d": depth}
        for name, h in hints.items()
    ]
    result = await session.execute(
        text(
            "INSERT INTO norms_players (username, hint_rapid, hint_blitz, depth) "
            "VALUES (:u, :r, :b, :d) ON CONFLICT (username) DO UPDATE SET "
            "hint_rapid = coalesce(norms_players.hint_rapid, excluded.hint_rapid), "
            "hint_blitz = coalesce(norms_players.hint_blitz, excluded.hint_blitz) "
            "WHERE norms_players.status = 'queued'"
        ),
        rows,
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def seed_from_working_db(work: AsyncSession, norms: AsyncSession) -> int:
    """Соперники из партий Chess.com рабочей БД (транзакция только для чтения)."""
    await work.execute(text("SET TRANSACTION READ ONLY"))
    rows = await work.execute(
        select(
            Game.white, Game.black, Game.white_elo, Game.black_elo, Game.user_color,
            Game.time_control,
        )
        .where(Game.source == GameSource.CHESSCOM, Game.user_color.is_not(None))
        .order_by(Game.played_at.desc().nulls_last())
    )  # fmt: skip
    hints: dict[str, dict[str, int]] = {}
    for row in rows:
        white = row.user_color == Color.BLACK
        name, elo = (row.white, row.white_elo) if white else (row.black, row.black_elo)
        tc = time_class(row.time_control)
        if elo is not None and tc in NORM_TIME_CLASSES:
            hints.setdefault(name.lower(), {}).setdefault(tc, int(elo))
    await work.rollback()
    added = await enqueue(norms, hints, depth=0)
    await norms.commit()
    return added


async def next_player(session: AsyncSession, deficits: Deficits) -> str | None:
    """Игрок из очереди для самой нужной группы, у которой есть кандидаты."""
    for tc, center in deficits.ranked():
        column = "hint_rapid" if tc == "rapid" else "hint_blitz"
        lo, hi = center - 50, center + 50
        name = await session.scalar(
            text(
                f"SELECT username FROM norms_players WHERE status = 'queued' "
                f"AND {column} >= :lo AND {column} < :hi "
                "ORDER BY depth, md5(username) LIMIT 1"
            ),
            {"lo": lo, "hi": hi},
        )
        if name is not None:
            return str(name)
    return None


# --- Шаги -------------------------------------------------------------------------------------


async def _store_months(
    session: AsyncSession, username: str, months: dict[date, list[MonthGame]]
) -> None:
    for month, games in months.items():
        await session.execute(
            text(
                "INSERT INTO norms_fetched (username, month) VALUES (:u, :m) ON CONFLICT DO NOTHING"
            ),
            {"u": username, "m": month},
        )
        for s in summarize(games):
            await session.execute(
                text(
                    "INSERT INTO norms_months (username, month, time_class, games, first_rating, "
                    "last_rating) VALUES (:u, :m, :tc, :g, :f, :l) ON CONFLICT DO NOTHING"
                ),
                {
                    "u": username,
                    "m": month,
                    "tc": s.time_class,
                    "g": s.games,
                    "f": s.first_rating,
                    "l": s.last_rating,
                },
            )


async def _taken_ids(session: AsyncSession, user: User, ids: Sequence[str]) -> set[str]:
    if not ids:
        return set()
    rows = await session.scalars(
        select(Game.external_id).where(Game.user_id == user.id, Game.external_id.in_(ids))
    )
    return set(rows)


async def sample_player(
    session: AsyncSession,
    fetcher: Fetcher,
    user: User,
    username: str,
    *,
    deficits: Deficits,
    targets: SampleTargets,
) -> int:
    """Отбирает партии игрока; возвращает число взятых."""
    depth = int(
        await session.scalar(
            text("SELECT depth FROM norms_players WHERE username = :u"), {"u": username}
        )
        or 0
    )
    try:
        archives = await fetcher.archives(username)
    except PlayerGoneError:
        await _set_status(session, username, "failed")
        return 0
    await session.execute(
        text("UPDATE norms_players SET archives = :a WHERE username = :u"),
        {"a": archives, "u": username},
    )
    needed = deficits.needed()
    picked: list[MonthGame] = []
    months: dict[date, list[MonthGame]] = {}
    for month in completed_months(archives, datetime.now(UTC).date())[: targets.sample_months]:
        try:
            games = parse_month(await fetcher.month(username, month), username)
        except PlayerGoneError:
            break
        months[month] = games
        taken: Counter[str] = Counter(g.time_class for g in picked)
        exclude = await _taken_ids(session, user, [g.external_id for g in games])
        exclude |= {g.external_id for g in picked}
        picked += pick_samples(
            games, needed, dict(taken), exclude=exclude, per_player=targets.games_per_player
        )
        if _sampled_enough(picked, months, needed, targets):
            break
    await _store_months(session, username, months)
    await _save_samples(session, user, username, picked)
    all_games = [g for games in months.values() for g in games]
    await enqueue(session, opponents(all_games, MAX_NEW_OPPONENTS, username), depth + 1)
    await _set_status(session, username, "sampled")
    return len(picked)


def _sampled_enough(
    picked: Sequence[MonthGame],
    months: dict[date, list[MonthGame]],
    needed: dict[tuple[str, int], int],
    targets: SampleTargets,
) -> bool:
    """Дальше в архив не идти: по каждому контролю норма набрана, либо в просмотренных месяцах
    у игрока нет рейтинговых партий этого контроля, либо его группа уже набрана."""
    done = Counter(g.time_class for g in picked)
    seen = [g for games in months.values() for g in games if g.rated]
    for tc in NORM_TIME_CLASSES:
        if done[tc] >= targets.games_per_player:
            continue
        latest = next((g for g in seen if g.time_class == tc), None)
        center = None if latest is None else nearest_center(latest.rating)
        if center is not None and needed.get((tc, center), 0) > 0:
            return False
    return True


async def _save_samples(
    session: AsyncSession, user: User, username: str, picked: Sequence[MonthGame]
) -> None:
    imported = []
    for g in picked:
        game = convert(SourceGame(external_id=g.external_id, pgn=g.pgn), username)
        if game is not None and game.user_color == g.color:
            imported.append((g, game))
    if not imported:
        return
    await insert_games(session, user, GameSource.CHESSCOM, [game for _, game in imported])
    ids = await session.execute(
        select(Game.external_id, Game.id).where(
            Game.user_id == user.id, Game.external_id.in_([g.external_id for g, _ in imported])
        )
    )
    by_ext = {row.external_id: row.id for row in ids}
    for g, _ in imported:
        center = nearest_center(g.rating)
        if g.external_id in by_ext and center is not None:
            await session.execute(
                text(
                    "INSERT INTO norms_samples (game_id, username, time_class, rating, center) "
                    "VALUES (:g, :u, :tc, :r, :c) ON CONFLICT DO NOTHING"
                ),
                {"g": by_ext[g.external_id], "u": username, "tc": g.time_class, "r": g.rating,
                 "c": center},
            )  # fmt: skip


async def _set_status(session: AsyncSession, username: str, status: str) -> None:
    await session.execute(
        text("UPDATE norms_players SET status = :s, sampled_at = now() WHERE username = :u"),
        {"s": status, "u": username},
    )
    await session.commit()


def completed_months(archives: Sequence[date], today: date) -> list[date]:
    """Месяцы до текущего: их архивы у Chess.com закэшированы и отдаются быстро, а текущий
    собирается на лету и у активных игроков идёт минутами."""
    current = today.replace(day=1)
    return [m for m in archives if m < current]


def trajectory_months(archives: Sequence[date], today: date, targets: SampleTargets) -> list[date]:
    """Месяцы архива для траектории: не старше `trajectory_months`, через `stride` от
    самого нового месяца с партиями."""
    completed = completed_months(archives, today)
    if not completed:
        return []
    index = completed[0].year * 12 + completed[0].month
    oldest = today.year * 12 + today.month - targets.trajectory_months
    return [
        m
        for m in completed
        if m.year * 12 + m.month > oldest
        and (index - (m.year * 12 + m.month)) % targets.trajectory_stride == 0
    ]


async def trajectory_player(
    session: AsyncSession, fetcher: Fetcher, username: str, targets: SampleTargets
) -> int:
    """Догружает месяцы траектории игрока; возвращает число запросов."""
    archives = await session.scalar(
        text("SELECT archives FROM norms_players WHERE username = :u"), {"u": username}
    )
    fetched = set(
        await session.scalars(
            text("SELECT month FROM norms_fetched WHERE username = :u"), {"u": username}
        )
    )
    wanted = [
        m
        for m in trajectory_months(list(archives or []), datetime.now(UTC).date(), targets)
        if m not in fetched
    ]
    status = "done"
    for month in wanted:
        try:
            games = parse_month(await fetcher.month(username, month), username)
        except PlayerGoneError:
            status = "failed"
            break
        await _store_months(session, username, {month: games})
        await session.commit()
    await session.execute(
        text("UPDATE norms_players SET traj_status = :s, traj_at = now() WHERE username = :u"),
        {"s": status, "u": username},
    )
    await session.commit()
    return len(wanted)


async def next_trajectory(session: AsyncSession) -> str | None:
    """Отобранный игрок с партиями в выборке, у которого траектория ещё не собрана."""
    name = await session.scalar(
        text(
            "SELECT p.username FROM norms_players p WHERE p.status = 'sampled' "
            "AND p.traj_status = 'pending' "
            "AND EXISTS (SELECT 1 FROM norms_samples s WHERE s.username = p.username "
            "AND s.center = ANY(:bands)) "
            "ORDER BY (SELECT min(CASE WHEN s.time_class = 'rapid' THEN 0 ELSE 1 END) "
            "FROM norms_samples s WHERE s.username = p.username), p.sampled_at LIMIT 1"
        ),
        {"bands": list(PRIORITY_BANDS)},
    )
    return None if name is None else str(name)


# --- Цикл -------------------------------------------------------------------------------------


async def crawl(
    norms_maker: async_sessionmaker[AsyncSession],
    work_maker: async_sessionmaker[AsyncSession] | None,
    fetcher: Fetcher,
    *,
    targets: SampleTargets = TARGETS,
    trajectory_every: int = 3,
    max_steps: int | None = None,
    trajectories: bool = True,
) -> None:
    """Шаг — один игрок выборки; каждый `trajectory_every`-й шаг (и когда выборка набрана) —
    ещё траектория одного игрока. Выход — когда делать нечего или исчерпан `max_steps`."""
    async with norms_maker() as session:
        await ensure_schema(session)
        user = await service_user(session)
        queued = await session.scalar(text("SELECT count(*) FROM norms_players"))
        if not queued and work_maker is not None:
            async with work_maker() as work:
                added = await seed_from_working_db(work, session)
            log.info("norms.crawl.seeded", players=added)
    step = 0
    while max_steps is None or step < max_steps:
        step += 1
        async with norms_maker() as session:
            deficits = await load_deficits(session, targets)
            player = await next_player(session, deficits)
            if player is not None:
                taken = await sample_player(
                    session, fetcher, user, player, deficits=deficits, targets=targets
                )
                log.info(
                    "norms.crawl.sampled", step=step, taken=taken, requests=fetcher.requests,
                    open_groups=len(deficits.ranked()),
                )  # fmt: skip
            if trajectories and (player is None or step % trajectory_every == 0):
                traj = await next_trajectory(session)
                if traj is not None:
                    await trajectory_player(session, fetcher, traj, targets)
                elif player is None:
                    break
            elif player is None:
                break
    log.info("norms.crawl.finished", steps=step, requests=fetcher.requests)
