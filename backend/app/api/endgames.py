"""Тренажёр эндшпиля (сессия 16.3): каталог типовых позиций, позиции из своих партий,
таблицы Syzygy, попытки."""

from typing import Annotated

import chess
import structlog
from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import Scope, UserLimiterDep
from app.api.schemas_endgames import (
    AttemptIn,
    CatalogOut,
    CatalogPositionOut,
    GamePositionOut,
    MineOut,
    ProgressOut,
    TablebaseMoveOut,
    TablebaseOut,
)
from app.endgames import queries
from app.endgames.catalog import CATALOG, Category, catalog_position
from app.endgames.tablebase import (
    TB_MAX_PIECES,
    Tablebase,
    TablebaseUnavailableError,
    make_tablebase,
    piece_count,
)
from app.importers.http import make_http_client

router = APIRouter(tags=["endgames"])
log = structlog.get_logger(__name__)

# Вид лимита `tablebase` (`RATE_LIMIT_TABLEBASE`).
TABLEBASE_SCOPE: Scope = "tablebase"


def get_tablebase(request: Request) -> Tablebase:
    """Один клиент таблиц на процесс (пауза и «один запрос за раз» — на весь API). Создаётся
    в lifespan (`app/main.py`); без lifespan — при первом запросе. Тесты подменяют
    `app.state.tablebase` фейком."""
    state = request.app.state
    tablebase: Tablebase | None = getattr(state, "tablebase", None)
    if tablebase is None:
        tablebase = make_tablebase(state.settings, make_http_client(state.settings), state.db)
        state.tablebase = tablebase
    return tablebase


TablebaseDep = Annotated[Tablebase, Depends(get_tablebase)]


def _invalid_fen(message: str) -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_FEN, message)


def _not_found() -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.ENDGAME_NOT_FOUND, "Позиция не найдена")


@router.get("/endgames/catalog")
async def endgames_catalog(session: SessionDep, user: CurrentUser) -> CatalogOut:
    """Типовые позиции с прогрессом пользователя."""
    stats = await queries.progress(session, user.id, "catalog")
    positions = []
    for position in CATALOG:
        board = chess.Board(position.fen)
        done = stats.get(position.id, queries.Progress())
        positions.append(
            CatalogPositionOut(
                id=position.id,
                category=position.category,
                fen=position.fen,
                goal=position.goal,
                difficulty=position.difficulty,
                color="white" if board.turn == chess.WHITE else "black",
                pieces=piece_count(board),
                attempts=done.attempts,
                successes=done.successes,
            )
        )
    return CatalogOut(categories=list(Category), positions=positions)


@router.get("/endgames/mine")
async def endgames_mine(
    session: SessionDep,
    user: CurrentUser,
    settings: SettingsDep,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> MineOut:
    """Позиции из своих партий: ошибка в эндшпиле, цель — по win% до хода."""
    size = min(limit or settings.endgames_mine_limit, settings.endgames_mine_limit)
    rows = await queries.game_positions(session, user.id, limit=size)
    return MineOut(
        positions=[
            GamePositionOut(
                key=row.key,
                fen=row.fen,
                goal=row.goal,
                game_id=row.game_id,
                ply=row.ply,
                played_at=row.played_at,
                opponent=row.opponent,
                san=row.san,
                best_san=row.best_san,
                win_before=row.win_before,
                pieces=row.pieces,
                attempts=row.progress.attempts,
                successes=row.progress.successes,
            )
            for row in rows
        ]
    )


@router.get("/endgames/tablebase")
async def endgames_tablebase(
    tablebase: TablebaseDep,
    user: CurrentUser,
    limiter: UserLimiterDep,
    fen: Annotated[str, Query(max_length=100)],
) -> TablebaseOut:
    """Ответ таблиц Syzygy для позиции ≤ 7 фигур глазами ходящего."""
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise _invalid_fen("Некорректный FEN") from exc
    if not board.is_valid():
        raise _invalid_fen("Невозможная позиция")
    if piece_count(board) > TB_MAX_PIECES:
        raise _invalid_fen(f"В таблицах — позиции не больше {TB_MAX_PIECES} фигур")
    await limiter.hit(TABLEBASE_SCOPE)
    try:
        position = await tablebase.probe(board)
    except TablebaseUnavailableError as exc:
        log.warning("endgames.tablebase_unavailable", error=str(exc))
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorCode.TABLEBASE_UNAVAILABLE,
            f"Таблицы Lichess недоступны: {exc}",
        ) from exc
    return TablebaseOut(
        category=position.category,
        dtz=position.dtz,
        dtm=position.dtm,
        checkmate=position.checkmate,
        stalemate=position.stalemate,
        moves=[
            TablebaseMoveOut(uci=m.uci, san=m.san, category=m.category, dtz=m.dtz, dtm=m.dtm)
            for m in position.moves
        ],
    )


@router.post("/endgames/attempts")
async def endgames_attempt(body: AttemptIn, session: SessionDep, user: CurrentUser) -> ProgressOut:
    """Записать попытку; ответ — прогресс по этой позиции."""
    if body.source == "catalog":
        position = catalog_position(body.key)
        if position is None:
            raise _not_found()
        if body.goal != position.goal:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                ErrorCode.VALIDATION_ERROR,
                f"Цель позиции каталога — {position.goal}",
            )
    elif not (body.key.isdigit() and len(body.key) <= 18) or not await queries.own_move_exists(
        session, user.id, int(body.key)
    ):
        raise _not_found()
    done = await queries.add_attempt(
        session,
        user.id,
        source=body.source,
        key=body.key,
        goal=body.goal,
        success=body.success,
        plies=body.plies,
    )
    return ProgressOut(attempts=done.attempts, successes=done.successes)
