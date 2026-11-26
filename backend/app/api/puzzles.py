"""Пазлы из ошибок пользователя: следующий пазл, попытка решения, темы и забеги на время.

Режимы (сессия 16.2): `srs` — повторение по коробкам Лейтнера; `practice` — любые пазлы по
фильтрам, сначала нерешённые и с низкой коробкой; `rush` — от коротких решений к длинным.
Попытки `practice` / `rush` пишутся с `mode`, но коробку и дату повторения не меняют, а серия
считается только по `srs`.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

import chess
from fastapi import APIRouter, Query, status
from sqlalchemy import ColumnElement, Select, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ApiError, ErrorCode
from app.api.schemas import (
    AttemptIn,
    AttemptOut,
    PuzzleCounts,
    PuzzleEco,
    PuzzleFilters,
    PuzzleLastMove,
    PuzzleMode,
    PuzzleNextOut,
    PuzzleOpeningStat,
    PuzzleOut,
    PuzzlePhaseStat,
    PuzzleSource,
    PuzzleTheme,
    PuzzleThemesOut,
    PuzzleThemeStat,
    RushOut,
    RushRunIn,
    RushRunItem,
    RushRunOut,
    RushVariant,
)
from app.db.models import Analysis, Color, Game, Move, Puzzle, PuzzleAttempt, PuzzleRushRun
from app.puzzles.rush import (
    RunInvalidError,
    attempt_window,
    check_run_shape,
    check_score_plausible,
)
from app.puzzles.solution import AttemptError, check_attempt
from app.puzzles.srs import schedule
from app.review.types import Phase

router = APIRouter(tags=["puzzles"])

# Не больше стольких id в `exclude` (пропущенные и уже показанные в этой сессии пазлы).
MAX_EXCLUDE = 100
SRS = "srs"
PRACTICE = "practice"
RUSH = "rush"
RECENT_RUNS = 10
# Забег идёт от коротких решений к длинным.
SOLUTION_LENGTH = func.coalesce(func.array_length(Puzzle.solution_uci, 1), 0)


def _now() -> datetime:
    return datetime.now(UTC)


def _with_source_joins[*Ts](stmt: Select[*Ts]) -> Select[*Ts]:
    """Пазл → ход-источник → разбор → партия (все связи необязательны)."""
    return (
        stmt.select_from(Puzzle)
        .outerjoin(Move, Move.id == Puzzle.move_id)
        .outerjoin(Analysis, Analysis.id == Move.analysis_id)
        .outerjoin(Game, Game.id == Analysis.game_id)
    )


def _filter_conditions(filters: PuzzleFilters) -> list[ColumnElement[bool]]:
    """Тема — в `themes` пазла, фаза — хода-источника, дебют — партии. Пазл без хода-источника
    (разбор удалён) под фильтр фазы или дебюта не попадает."""
    conditions: list[ColumnElement[bool]] = []
    if filters.theme is not None:
        conditions.append(Puzzle.themes.contains([filters.theme]))
    if filters.phase is not None:
        conditions.append(Move.phase == filters.phase)
    if filters.eco is not None:
        conditions.append(Game.opening_eco == filters.eco)
    return conditions


async def _streak(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Решённых подряд: попытки повторения (`srs`) после последней неудачной."""
    last_fail = (
        select(func.max(PuzzleAttempt.created_at))
        .where(PuzzleAttempt.user_id == user_id, PuzzleAttempt.mode == SRS, ~PuzzleAttempt.correct)
        .scalar_subquery()
    )
    streak = await session.scalar(
        select(func.count()).where(
            PuzzleAttempt.user_id == user_id,
            PuzzleAttempt.mode == SRS,
            PuzzleAttempt.correct,
            or_(last_fail.is_(None), PuzzleAttempt.created_at > last_fail),
        )
    )
    return streak or 0


async def _counts(
    session: AsyncSession, user_id: uuid.UUID, now: datetime, filters: PuzzleFilters
) -> PuzzleCounts:
    stmt = _with_source_joins(
        select(
            func.count().filter(Puzzle.next_review_at <= now).label("due"),
            func.count().filter(Puzzle.next_review_at.is_(None)).label("new"),
            func.count().label("total"),
            func.min(Puzzle.next_review_at).filter(Puzzle.next_review_at > now).label("next"),
        )
    ).where(Puzzle.user_id == user_id, *_filter_conditions(filters))
    row = (await session.execute(stmt)).one()
    return PuzzleCounts(
        due=row.due,
        new=row.new,
        total=row.total,
        streak=await _streak(session, user_id),
        next_review_at=row.next,
    )


def _san_line(fen: str, line: list[str]) -> list[str]:
    board = chess.Board(fen)
    result = []
    for uci in line:
        move = chess.Move.from_uci(uci)
        result.append(board.san(move))
        board.push(move)
    return result


@router.get("/puzzles/next")
async def next_puzzle(  # noqa: PLR0917
    session: SessionDep,
    user: CurrentUser,
    exclude: Annotated[list[uuid.UUID], Query(max_length=MAX_EXCLUDE)] = [],  # noqa: B006
    mode: PuzzleMode = "srs",
    theme: PuzzleTheme | None = None,
    phase: Phase | None = None,
    eco: PuzzleEco | None = None,
) -> PuzzleNextOut:
    """Следующий пазл по режиму и фильтрам (`theme`, `phase` хода-источника, `eco` партии).

    - `srs`: сначала пора повторить (раньше назначенные первыми), затем новые — из более
      свежих партий;
    - `practice`: любые подходящие — сначала нерешённые, затем с низкой коробкой, затем
      давно не решавшиеся;
    - `rush`: любые подходящие, от коротких решений к длинным (внутри длины — вперемешку).

    `exclude` — уже показанные клиентом в этой сессии: повторов в нём не бывает.
    `counts` считаются среди пазлов под фильтрами."""
    now = _now()
    filters = PuzzleFilters(theme=theme, phase=phase, eco=eco)
    prev = aliased(Move)
    due = Puzzle.next_review_at <= now
    stmt = (
        _with_source_joins(select(Puzzle, Move, Game, prev))
        .outerjoin(prev, and_(prev.analysis_id == Move.analysis_id, prev.ply == Move.ply - 1))
        .where(Puzzle.user_id == user.id, *_filter_conditions(filters))
        .limit(1)
    )
    recent = (Game.played_at.desc().nulls_last(), Move.ply, Puzzle.id)
    if mode == SRS:
        stmt = stmt.where(or_(due, Puzzle.next_review_at.is_(None))).order_by(
            case((due, 0), else_=1), Puzzle.next_review_at, *recent
        )
    elif mode == PRACTICE:
        stmt = stmt.order_by(
            Puzzle.solved, Puzzle.box, Puzzle.last_attempt_at.asc().nulls_first(), *recent
        )
    else:
        stmt = stmt.order_by(SOLUTION_LENGTH, func.random())
    if exclude:
        stmt = stmt.where(Puzzle.id.not_in(exclude))
    found = (await session.execute(stmt)).one_or_none()
    counts = await _counts(session, user.id, now, filters)
    if found is None:
        return PuzzleNextOut(puzzle=None, counts=counts)

    puzzle, move, game, prev_move = found
    board = chess.Board(puzzle.fen)
    source = None
    if move is not None and game is not None:
        source = PuzzleSource(
            game_id=game.id,
            ply=move.ply,
            fullmove=board.fullmove_number,
            san=move.san,
            move_class=move.move_class,
            is_miss=move.is_miss,
            opponent=game.black if game.user_color == Color.WHITE else game.white,
            played_at=game.played_at,
        )
    last_move = None
    if prev_move is not None:
        last_move = PuzzleLastMove(
            uci=prev_move.uci, san=prev_move.san, fen_before=prev_move.fen_before
        )
    return PuzzleNextOut(
        puzzle=PuzzleOut(
            id=puzzle.id,
            fen=puzzle.fen,
            color=Color.WHITE if board.turn == chess.WHITE else Color.BLACK,
            themes=puzzle.themes,
            player_moves=(len(puzzle.solution_uci) + 1) // 2,
            hints=[uci[:2] for uci in puzzle.solution_uci[::2]],
            box=puzzle.box,
            attempts=puzzle.attempts,
            next_review_at=puzzle.next_review_at,
            last_move=last_move,
            source=source,
        ),
        counts=counts,
    )


@router.get("/puzzles/themes")
async def puzzle_themes(session: SessionDep, user: CurrentUser) -> PuzzleThemesOut:
    """Числа для выбора на экране «По темам»: темы (всего / пора повторить / решено), три
    фазы хода-источника и дебюты партий. Пазл с несколькими темами учтён в каждой."""
    now = _now()
    exploded = (
        select(
            func.unnest(Puzzle.themes).label("theme"),
            Puzzle.next_review_at.label("next_review_at"),
            Puzzle.solved.label("solved"),
        )
        .where(Puzzle.user_id == user.id)
        .subquery()
    )
    theme_rows = await session.execute(
        select(
            exploded.c.theme,
            func.count().label("total"),
            func.count().filter(exploded.c.next_review_at <= now).label("due"),
            func.count().filter(exploded.c.solved).label("solved"),
        )
        .group_by(exploded.c.theme)
        .order_by(func.count().desc(), exploded.c.theme)
    )
    phase_rows = await session.execute(
        _with_source_joins(
            select(
                Move.phase,
                func.count().label("total"),
                func.count().filter(Puzzle.solved).label("solved"),
            )
        )
        .where(Puzzle.user_id == user.id, Move.phase.is_not(None))
        .group_by(Move.phase)
    )
    by_phase = {r.phase: r for r in phase_rows}
    opening_rows = await session.execute(
        _with_source_joins(
            select(Game.opening_eco, func.min(Game.opening_name).label("name"), func.count())
        )
        .where(Puzzle.user_id == user.id, Game.opening_eco.is_not(None))
        .group_by(Game.opening_eco)
        .order_by(func.count().desc(), Game.opening_eco)
    )
    return PuzzleThemesOut(
        themes=[
            PuzzleThemeStat(theme=r.theme, total=r.total, due=r.due, solved=r.solved)
            for r in theme_rows
        ],
        phases=[
            PuzzlePhaseStat(
                phase=phase,
                total=by_phase[phase].total if phase in by_phase else 0,
                solved=by_phase[phase].solved if phase in by_phase else 0,
            )
            for phase in Phase
        ],
        openings=[
            PuzzleOpeningStat(eco=eco, name=name, total=total) for eco, name, total in opening_rows
        ],
    )


@router.post("/puzzles/{puzzle_id}/attempt")
async def attempt_puzzle(
    puzzle_id: uuid.UUID, body: AttemptIn, session: SessionDep, user: CurrentUser
) -> AttemptOut:
    """Проверка ходов на сервере. Пока ходы верны и решение не закончено — `continue` с
    ответом соперника (ничего не записывается); `solved` / `failed` записывают попытку.
    В `srs` ещё и назначают следующее повторение; в `practice` / `rush` коробка и дата
    повторения остаются как были (но счётчик попыток и результат последней попытки
    обновляются)."""
    puzzle = await session.scalar(
        select(Puzzle).where(Puzzle.id == puzzle_id, Puzzle.user_id == user.id).with_for_update()
    )
    if puzzle is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.PUZZLE_NOT_FOUND, "Пазл не найден")
    try:
        check = check_attempt(puzzle.fen, puzzle.solution_uci, body.moves_uci, gave_up=body.gave_up)
    except AttemptError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.PUZZLE_ATTEMPT_INVALID, str(exc)
        ) from exc
    if check.result == "continue":
        await session.rollback()
        return AttemptOut(result="continue", reply_uci=check.reply)

    now = _now()
    solved = check.result == "solved"
    if body.mode == SRS:
        review = schedule(puzzle.box, solved=solved, hint_used=body.hint_used, now=now)
        puzzle.box = review.box
        puzzle.next_review_at = review.next_review_at
    puzzle.attempts += 1
    puzzle.solved = solved
    puzzle.last_attempt_at = now
    session.add(
        PuzzleAttempt(
            puzzle_id=puzzle.id,
            user_id=user.id,
            correct=solved,
            hint_used=body.hint_used,
            mode=body.mode,
        )
    )
    await session.commit()
    return AttemptOut(
        result=check.result,
        expected_uci=check.expected,
        solution_uci=puzzle.solution_uci,
        solution_san=_san_line(puzzle.fen, puzzle.solution_uci),
        box=puzzle.box,
        next_review_at=puzzle.next_review_at,
        streak=await _streak(session, user.id),
    )


# --- Забеги «Пазлы на время» ---
# Таблица `puzzle_rush_runs` без колонки варианта, поэтому вариант лежит в `filters["variant"]`.


def _run_filters(run: PuzzleRushRun) -> PuzzleFilters:
    return PuzzleFilters.model_validate({k: v for k, v in run.filters.items() if k != "variant"})


async def _best_score(
    session: AsyncSession, user_id: uuid.UUID, variant: RushVariant
) -> int | None:
    return await session.scalar(
        select(func.max(PuzzleRushRun.score)).where(
            PuzzleRushRun.user_id == user_id, PuzzleRushRun.filters["variant"].astext == variant
        )
    )


@router.post("/puzzles/rush", status_code=status.HTTP_201_CREATED)
async def save_rush_run(body: RushRunIn, session: SessionDep, user: CurrentUser) -> RushRunOut:
    """Сохранить итог забега. Счёт не больше верных `rush`-попыток за время забега и минуту
    (и только после предыдущего забега: одни попытки дважды не засчитываются) — иначе 422."""
    now = _now()
    try:
        check_run_shape(
            body.variant, score=body.score, mistakes=body.mistakes, duration_s=body.duration_s
        )
    except RunInvalidError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.VALIDATION_ERROR, str(exc)
        ) from exc
    since = now - attempt_window(body.duration_s)
    last_run = await session.scalar(
        select(func.max(PuzzleRushRun.created_at)).where(PuzzleRushRun.user_id == user.id)
    )
    if last_run is not None:
        since = max(since, last_run)
    correct = await session.scalar(
        select(func.count()).where(
            PuzzleAttempt.user_id == user.id,
            PuzzleAttempt.mode == RUSH,
            PuzzleAttempt.correct,
            PuzzleAttempt.created_at >= since,
        )
    )
    try:
        check_score_plausible(body.score, correct or 0)
    except RunInvalidError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.VALIDATION_ERROR, str(exc)
        ) from exc

    previous = await _best_score(session, user.id, body.variant)
    run = PuzzleRushRun(
        user_id=user.id,
        score=body.score,
        mistakes=body.mistakes,
        duration_s=body.duration_s,
        filters=body.filters.model_dump(mode="json", exclude_none=True) | {"variant": body.variant},
    )
    session.add(run)
    await session.commit()
    is_best = body.score > (previous or 0)
    return RushRunOut(id=run.id, best=max(previous or 0, body.score), is_best=is_best)


@router.get("/puzzles/rush")
async def rush_runs(session: SessionDep, user: CurrentUser, variant: RushVariant) -> RushOut:
    """Рекорд по варианту и последние забеги (новые первыми)."""
    runs = await session.scalars(
        select(PuzzleRushRun)
        .where(PuzzleRushRun.user_id == user.id, PuzzleRushRun.filters["variant"].astext == variant)
        .order_by(PuzzleRushRun.created_at.desc(), PuzzleRushRun.id.desc())
        .limit(RECENT_RUNS)
    )
    return RushOut(
        best=await _best_score(session, user.id, variant),
        recent=[
            RushRunItem(
                id=run.id,
                score=run.score,
                mistakes=run.mistakes,
                duration_s=run.duration_s,
                filters=_run_filters(run),
                created_at=run.created_at,
            )
            for run in runs
        ],
    )
