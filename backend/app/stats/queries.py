"""Статистика пользователя по многим партиям (SPEC §8 `GET /stats/me`, §9 `/stats`).

Все агрегаты считает PostgreSQL: ходы в Python не загружаются. Учитываются только партии
с известным цветом пользователя (`games.user_color`) и только его ходы; партии без цвета
лишь подсчитываются. Анализ партии — последний (как в списке партий и на плашках), фазы,
классы и мотивы — только у готового.
"""

import uuid
from collections import defaultdict
from typing import Any, NamedTuple

from sqlalchemy import (
    ColumnElement,
    Float,
    Integer,
    Numeric,
    Select,
    String,
    and_,
    case,
    cast,
    column,
    func,
    literal_column,
    null,
    or_,
    select,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import CTE

from app.api.schemas import (
    AccuracyPoint,
    AccuracySeries,
    BrilliantMove,
    BrilliantStats,
    ClassesStats,
    ClassStat,
    ClockBucketStat,
    MotifExample,
    MotifStat,
    OpeningsStats,
    OpeningStat,
    PhaseStat,
    PhaseTimeStat,
    RatingGroupStat,
    StatsFilters,
    StatsOut,
    StatsTotals,
    TimeStats,
)
from app.db.accuracy import accuracy_sql
from app.db.models import Analysis, AnalysisStatus, Color, Game, GameSource, Move
from app.explain.facts import ERRORS
from app.review.clock import FAST_MIN_CS, FAST_SHARE, TROUBLE_SHARE
from app.review.game_rating import CURVES, DAILY_SHIFT, TimeClass
from app.review.types import MoveClass, Phase

# Скользящее среднее точности — по стольким последним партиям.
ACCURACY_WINDOW = 10
# Точек на графике точности — последние N партий.
STATS_MAX_POINTS = 500
TOP_OPENINGS = 8
TOP_MOTIFS = 6
MOTIF_EXAMPLES = 3
# Блестящих ходов в ответе — последние N (счётчики — по всем).
BRILLIANT_LIMIT = 100

_EMPTY_JSON_ARRAY = literal_column("'[]'::jsonb", JSONB)


def time_class_sql(time_control: ColumnElement[Any]) -> ColumnElement[str]:
    """SQL-версия `review.game_rating.time_class` (совпадение проверяет тест)."""
    base = cast(func.substring(time_control, r"^(\d+)"), Numeric)
    increment = func.coalesce(cast(func.substring(time_control, r"^\d+\+(\d+)$"), Numeric), 0)
    total = base + 40 * increment
    return case(
        (time_control.like("1/%"), "daily"),
        (
            time_control.regexp_match(r"^\d+(\+\d+)?$"),
            case((total < 180, "bullet"), (total < 600, "blitz"), else_="rapid"),
        ),
        else_="rapid",
    )


def group_accuracy_sql(
    rating: ColumnElement[Any], time_class: ColumnElement[Any]
) -> ColumnElement[float]:
    """SQL-версия `review.game_rating.expected_accuracy` (совпадение проверяет тест):
    a − b·e^(−r/c), daily — кривая рапида со сдвигом."""
    rapid = CURVES["rapid"]
    curves = {**CURVES, "daily": (rapid[0] + DAILY_SHIFT, rapid[1], rapid[2])}
    return case(
        *(
            (time_class == name, a - b * func.exp(-cast(rating, Numeric) / c))
            for name, (a, b, c) in curves.items()
        ),
        else_=null(),
    )


def user_games(user_id: uuid.UUID, source: GameSource | None, tc: TimeClass | None) -> CTE:
    """Партии пользователя после фильтров + последний анализ + показываемая точность."""
    game = Game.__table__
    latest = (
        select(
            Analysis.id,
            Analysis.status,
            Analysis.white_accuracy,
            Analysis.black_accuracy,
            Analysis.cc_white_accuracy,
            Analysis.cc_black_accuracy,
            Analysis.phase_accuracy,
        )
        .where(Analysis.game_id == game.c.id)
        .order_by(Analysis.created_at.desc(), Analysis.id)
        .limit(1)
        .lateral("la")
    )
    user_color = game.c.user_color
    accuracy, kind = accuracy_sql(game, latest, user_color)
    time_class = time_class_sql(game.c.time_control)
    rating = case((user_color == Color.WHITE, game.c.white_elo), else_=game.c.black_elo)
    # Рейтинговая группа: кривые подобраны по рейтингам и точности Chess.com.
    group = case(
        (
            and_(
                game.c.source == GameSource.CHESSCOM,
                rating.is_not(None),
                kind.in_(["official", "cc"]),
            ),
            cast(group_accuracy_sql(rating, time_class), Float),
        ),
        else_=null(),
    )
    outcome = case(
        (game.c.result == "1/2-1/2", "draw"),
        (
            or_(
                and_(game.c.result == "1-0", user_color == Color.WHITE),
                and_(game.c.result == "0-1", user_color == Color.BLACK),
            ),
            "win",
        ),
        (game.c.result.in_(["1-0", "0-1"]), "loss"),
        else_=null(),
    )
    stmt = (
        select(
            game.c.id,
            func.coalesce(game.c.played_at, game.c.created_at).label("ts"),
            game.c.played_at,
            user_color.label("user_color"),
            game.c.opening_eco,
            game.c.opening_name,
            case((user_color == Color.WHITE, game.c.black), else_=game.c.white).label("opponent"),
            time_class.label("time_class"),
            outcome.label("outcome"),
            latest.c.id.label("analysis_id"),
            func.coalesce(latest.c.status == AnalysisStatus.DONE, False).label("done"),
            latest.c.phase_accuracy,
            accuracy.label("accuracy"),
            kind.label("accuracy_kind"),
            rating.label("rating"),
            group.label("group_accuracy"),
            game.c.clocks,
            game.c.move_times,
            (cast(func.substring(game.c.time_control, r"^(\d+)(?:\+\d+)?$"), Integer) * 100).label(
                "base_cs"
            ),
        )
        .select_from(game)
        .outerjoin(latest, true())
        .where(game.c.user_id == user_id)
    )
    if source is not None:
        stmt = stmt.where(game.c.source == source)
    if tc is not None:
        stmt = stmt.where(time_class == tc)
    return stmt.cte("ug")


def own_move(ug: CTE) -> ColumnElement[bool]:
    """Ход сделал пользователь: сторона на ходу в `fen_before` = его цвет."""
    side = func.split_part(Move.fen_before, " ", 2)
    return side == case((ug.c.user_color == Color.WHITE, "w"), else_="b")


def analyzed_moves[*Ts](stmt: Select[*Ts], ug: CTE) -> Select[*Ts]:
    return stmt.join(ug, Move.analysis_id == ug.c.analysis_id).where(ug.c.done, own_move(ug))


async def _totals(session: AsyncSession, ug: CTE) -> StatsTotals:
    own = ug.c.user_color.is_not(None)
    row = (
        await session.execute(
            select(
                func.count().filter(own).label("games"),
                func.count().filter(~own).label("games_without_color"),
                func.count().filter(own, ug.c.done).label("analyzed"),
                func.count().filter(own, ug.c.outcome == "win").label("wins"),
                func.count().filter(own, ug.c.outcome == "draw").label("draws"),
                func.count().filter(own, ug.c.outcome == "loss").label("losses"),
                func.avg(ug.c.accuracy).filter(own).label("accuracy"),
                func.count(ug.c.accuracy).filter(own).label("with_accuracy"),
            )
        )
    ).one()
    return StatsTotals.model_validate(row._asdict())


async def _accuracy_series(session: AsyncSession, ug: CTE) -> AccuracySeries:
    series = (
        select(
            ug,
            func.avg(ug.c.accuracy)
            .over(order_by=(ug.c.ts, ug.c.id), rows=(-(ACCURACY_WINDOW - 1), 0))
            .label("moving_avg"),
            func.avg(ug.c.group_accuracy)
            .over(order_by=(ug.c.ts, ug.c.id), rows=(-(ACCURACY_WINDOW - 1), 0))
            .label("group_moving_avg"),
        )
        .where(ug.c.user_color.is_not(None), ug.c.accuracy.is_not(None))
        .subquery()
    )
    rows = (
        await session.execute(
            select(series).order_by(series.c.ts.desc(), series.c.id.desc()).limit(STATS_MAX_POINTS)
        )
    ).all()
    return AccuracySeries(
        window=ACCURACY_WINDOW,
        points=[
            AccuracyPoint(
                game_id=row.id,
                played_at=row.played_at,
                accuracy=row.accuracy,
                kind=row.accuracy_kind,
                moving_avg=row.moving_avg,
                rating=row.rating,
                group_accuracy=row.group_accuracy,
                group_moving_avg=row.group_moving_avg if row.group_accuracy is not None else None,
                opponent=row.opponent,
                outcome=row.outcome,
                time_class=row.time_class,
                color=row.user_color,
            )
            for row in reversed(rows)
        ],
    )


async def _rating_groups(session: AsyncSession, ug: CTE) -> list[RatingGroupStat]:
    """Точность пользователя против рейтинговой группы — по контролям времени."""
    rows = await session.execute(
        select(
            ug.c.time_class,
            func.count().label("games"),
            func.round(func.avg(ug.c.rating)).label("rating"),
            func.avg(ug.c.accuracy).label("accuracy"),
            func.avg(ug.c.group_accuracy).label("group_accuracy"),
        )
        .where(
            ug.c.user_color.is_not(None),
            ug.c.accuracy.is_not(None),
            ug.c.group_accuracy.is_not(None),
        )
        .group_by(ug.c.time_class)
        .order_by(func.count().desc(), ug.c.time_class)
    )
    return [
        RatingGroupStat(
            time_class=row.time_class,
            games=row.games,
            rating=int(row.rating),
            accuracy=round(float(row.accuracy), 1),
            group_accuracy=round(float(row.group_accuracy), 1),
        )
        for row in rows
    ]


async def _openings(session: AsyncSession, ug: CTE) -> OpeningsStats:
    games = func.count()
    grouped = (
        select(
            ug.c.user_color,
            ug.c.opening_eco.label("eco"),
            ug.c.opening_name.label("name"),
            games.label("games"),
            func.count().filter(ug.c.outcome == "win").label("wins"),
            func.count().filter(ug.c.outcome == "draw").label("draws"),
            func.count().filter(ug.c.outcome == "loss").label("losses"),
            func.avg(ug.c.accuracy).label("accuracy"),
            func.row_number()
            .over(partition_by=ug.c.user_color, order_by=(games.desc(), ug.c.opening_name))
            .label("rank"),
        )
        .where(ug.c.user_color.is_not(None), ug.c.opening_name.is_not(None))
        .group_by(ug.c.user_color, ug.c.opening_eco, ug.c.opening_name)
        .subquery()
    )
    rows = await session.execute(
        select(grouped).where(grouped.c.rank <= TOP_OPENINGS).order_by(grouped.c.rank)
    )
    result: dict[Color, list[OpeningStat]] = {Color.WHITE: [], Color.BLACK: []}
    for row in rows:
        result[row.user_color].append(OpeningStat.model_validate(row._asdict()))
    return OpeningsStats(white=result[Color.WHITE], black=result[Color.BLACK])


async def _phases(session: AsyncSession, ug: CTE) -> list[PhaseStat]:
    columns = []
    for phase in Phase:
        value = cast(
            func.jsonb_extract_path_text(
                ug.c.phase_accuracy, cast(ug.c.user_color, String), phase.value
            ),
            Float,
        )
        columns += [func.avg(value).label(f"{phase}_avg"), func.count(value).label(f"{phase}_n")]
    row = (
        (await session.execute(select(*columns).where(ug.c.user_color.is_not(None), ug.c.done)))
        .one()
        ._mapping
    )
    return [
        PhaseStat(phase=phase, accuracy=row[f"{phase}_avg"], games=row[f"{phase}_n"])
        for phase in Phase
    ]


async def _classes(session: AsyncSession, ug: CTE, analyzed: int) -> ClassesStats:
    stmt = analyzed_moves(
        select(
            Move.move_class,
            func.count().label("n"),
            func.count().filter(Move.is_miss).label("misses"),
        ),
        ug,
    ).group_by(Move.move_class)
    counts: dict[MoveClass, int] = {}
    misses = 0
    for row in await session.execute(stmt):
        counts[row.move_class] = row.n
        misses += row.misses
    moves = sum(counts.values())

    def stat(key: MoveClass | str, count: int) -> ClassStat:
        return ClassStat.model_validate(
            {
                "move_class": key,
                "count": count,
                "per_game": round(count / analyzed, 2) if analyzed else 0.0,
                "share": round(100 * count / moves, 1) if moves else 0.0,
            }
        )

    items = [stat(cls, counts.get(cls, 0)) for cls in MoveClass]
    items.append(stat("miss", misses))
    return ClassesStats(games=analyzed, moves=moves, items=items)


async def _motifs(session: AsyncSession, ug: CTE) -> list[MotifStat]:
    """Мотивы, на которых пользователь терял: опровержения его ошибок и упущенное
    (как `_typical_errors` в `explain/facts.py`), по одному разу на ход."""
    motifs = func.coalesce(Move.motifs["refutation"], _EMPTY_JSON_ARRAY).op("||")(
        func.coalesce(Move.motifs["missed"], _EMPTY_JSON_ARRAY)
    )
    element = func.jsonb_array_elements(motifs).table_valued(column("value", JSONB)).lateral("el")
    errors = (
        analyzed_moves(
            select(
                Move.id.label("move_id"),
                Move.ply,
                Move.san,
                Move.fen_before,
                Move.move_class,
                Move.is_miss,
                ug.c.id.label("game_id"),
                ug.c.ts,
                ug.c.played_at,
                ug.c.opponent,
                element.c.value["type"].astext.label("type"),
            ),
            ug,
        )
        .join(element, true())
        .where(or_(Move.move_class.in_(ERRORS), Move.is_miss))
        .distinct()
        .subquery()
    )
    ranked = select(
        errors,
        func.count().over(partition_by=errors.c.type).label("n"),
        func.row_number()
        .over(partition_by=errors.c.type, order_by=(errors.c.ts.desc(), errors.c.ply))
        .label("example"),
    ).subquery()
    rows = await session.execute(
        select(ranked)
        .where(ranked.c.example <= MOTIF_EXAMPLES)
        .order_by(ranked.c.n.desc(), ranked.c.type, ranked.c.example)
    )
    counts: dict[str, int] = {}
    examples: dict[str, list[MotifExample]] = defaultdict(list)
    for row in rows:
        counts[row.type] = row.n
        _, side, *_, fullmove = row.fen_before.split()
        examples[row.type].append(
            MotifExample(
                game_id=row.game_id,
                move_id=row.move_id,
                ply=row.ply,
                fullmove=int(fullmove),
                color=Color.WHITE if side == "w" else Color.BLACK,
                san=row.san,
                move_class=row.move_class,
                is_miss=row.is_miss,
                played_at=row.played_at,
                opponent=row.opponent,
            )
        )
    top = sorted(counts, key=lambda kind: (-counts[kind], kind))[:TOP_MOTIFS]
    return [MotifStat(type=kind, count=counts[kind], examples=examples[kind]) for kind in top]


async def _brilliant(session: AsyncSession, ug: CTE) -> BrilliantStats:
    """Блестящие ходы пользователя (как раздел Brilliant moves у Chess.com)."""
    brilliant = Move.move_class == MoveClass.BRILLIANT
    totals = (
        await session.execute(
            analyzed_moves(
                select(
                    func.count().label("count"),
                    func.count(func.distinct(ug.c.id)).label("games"),
                ).select_from(Move),
                ug,
            ).where(brilliant)
        )
    ).one()
    rows = await session.execute(
        analyzed_moves(
            select(
                Move.id.label("move_id"),
                Move.ply,
                Move.san,
                Move.uci,
                Move.fen_before,
                ug.c.id.label("game_id"),
                ug.c.played_at,
                ug.c.opponent,
                ug.c.time_class,
                ug.c.outcome,
            ),
            ug,
        )
        .where(brilliant)
        .order_by(ug.c.ts.desc(), ug.c.id, Move.ply)
        .limit(BRILLIANT_LIMIT)
    )
    moves = []
    for row in rows:
        _, side, *_, fullmove = row.fen_before.split()
        moves.append(
            BrilliantMove(
                **row._asdict(),
                fullmove=int(fullmove),
                color=Color.WHITE if side == "w" else Color.BLACK,
            )
        )
    return BrilliantStats(count=totals.count, games=totals.games, moves=moves)


# Серьёзные ошибки для статистики времени: неточности слишком шумят.
_TIME_ERRORS = (MoveClass.MISTAKE, MoveClass.BLUNDER)
_CLOCK_BUCKETS = ("over_half", "quarter_half", "tenth_quarter", "under_tenth")


class ClockSql(NamedTuple):
    """Часы хода в SQL (`app/review/clock.py`): база, потрачено, остаток перед ходом,
    флаги цейтнота и быстрого хода; `known` — условия, при которых всё это известно."""

    base: ColumnElement[Any]
    spent: ColumnElement[Any]
    before: ColumnElement[Any]
    trouble: ColumnElement[bool]
    fast: ColumnElement[bool]
    known: tuple[ColumnElement[bool], ...]


def clock_sql(ug: CTE) -> ClockSql:
    base = ug.c.base_cs
    spent = ug.c.move_times[Move.ply]
    before = case((Move.ply <= 2, base), else_=ug.c.clocks[Move.ply - 2])
    return ClockSql(
        base=base,
        spent=spent,
        before=before,
        trouble=before < TROUBLE_SHARE * base,
        fast=spent <= func.greatest(FAST_MIN_CS, FAST_SHARE * base),
        known=(ug.c.move_times.is_not(None), base > 0, spent.is_not(None), before.is_not(None)),
    )


async def _time(session: AsyncSession, ug: CTE) -> TimeStats | None:
    """Время на ход по часам партии (`app/review/clock.py`; флаги совпадают — проверяет тест)."""
    base, spent, before, trouble, fast, known = clock_sql(ug)
    share = cast(before, Float) / base
    bucket = case(
        (share > 0.5, "over_half"),
        (share >= 0.25, "quarter_half"),
        (share >= TROUBLE_SHARE, "tenth_quarter"),
        else_="under_tenth",
    ).label("bucket")
    error = Move.move_class.in_(_TIME_ERRORS)

    def timed[*Ts](stmt: Select[*Ts]) -> Select[*Ts]:
        return analyzed_moves(stmt, ug).where(*known)

    totals = (
        await session.execute(
            timed(
                select(
                    func.count().label("moves"),
                    func.count(func.distinct(ug.c.id)).label("games"),
                    func.count(func.distinct(ug.c.id)).filter(trouble).label("trouble_games"),
                    func.count().filter(error).label("errors"),
                    func.count().filter(error, trouble).label("trouble_errors"),
                    func.count().filter(error, fast, ~trouble).label("hasty_errors"),
                )
            )
        )
    ).one()
    if not totals.moves:
        return None
    by_bucket = {
        row.bucket: row
        for row in await session.execute(
            timed(
                select(
                    bucket,
                    func.count().label("moves"),
                    func.avg(Move.accuracy).label("accuracy"),
                    func.count().filter(error).label("errors"),
                )
            ).group_by(bucket)
        )
    }
    by_phase = {
        row.phase: row
        for row in await session.execute(
            timed(
                select(Move.phase, func.count().label("moves"), func.avg(spent).label("spent"))
            ).group_by(Move.phase)
        )
    }

    def bucket_stat(name: str) -> ClockBucketStat:
        row = by_bucket.get(name)
        moves = row.moves if row else 0
        return ClockBucketStat.model_validate(
            {
                "bucket": name,
                "moves": moves,
                "accuracy": round(row.accuracy, 1) if row else None,
                "errors_per_100": round(100 * row.errors / moves, 1) if row else None,
            }
        )

    return TimeStats(
        games=totals.games,
        moves=totals.moves,
        trouble_games=totals.trouble_games,
        buckets=[bucket_stat(name) for name in _CLOCK_BUCKETS],
        phases=[
            PhaseTimeStat(
                phase=phase,
                moves=by_phase[phase].moves if phase in by_phase else 0,
                avg_spent_cs=round(by_phase[phase].spent) if phase in by_phase else None,
            )
            for phase in Phase
        ],
        errors=totals.errors,
        trouble_errors=totals.trouble_errors,
        hasty_errors=totals.hasty_errors,
    )


async def user_stats(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    source: GameSource | None = None,
    time_class: TimeClass | None = None,
) -> StatsOut:
    ug = user_games(user_id, source, time_class)
    totals = await _totals(session, ug)
    return StatsOut(
        filters=StatsFilters(source=source, time_class=time_class),
        totals=totals,
        accuracy=await _accuracy_series(session, ug),
        openings=await _openings(session, ug),
        phases=await _phases(session, ug),
        classes=await _classes(session, ug, totals.analyzed),
        motifs=await _motifs(session, ug),
        brilliant=await _brilliant(session, ug),
        rating_groups=await _rating_groups(session, ug),
        time=await _time(session, ug),
    )
