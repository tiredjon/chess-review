"""Lichess Opening Explorer через кэш: статистика ходов мастеров и образцовые партии (сессия 13)."""

from typing import Annotated, Literal

import chess
from fastapi import APIRouter, Depends, Path, Query, Request, status
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import limit_user
from app.explorer.types import (
    ExplorerMove,
    ExplorerPosition,
    ExplorerSource,
    ExplorerUnavailableError,
    MasterGamePgn,
    MasterGameRef,
    OpeningExplorer,
)

router = APIRouter(tags=["explorer"])


class ExplorerMoveOut(BaseModel):
    uci: str
    san: str
    white: int
    draws: int
    black: int
    games: int
    average_rating: int | None

    @classmethod
    def of(cls, move: ExplorerMove) -> "ExplorerMoveOut":
        return cls(
            uci=move.uci,
            san=move.san,
            white=move.white,
            draws=move.draws,
            black=move.black,
            games=move.games,
            average_rating=move.average_rating,
        )


class MasterGameRefOut(BaseModel):
    id: str
    white: str
    black: str
    white_rating: int | None
    black_rating: int | None
    year: int | None
    winner: Literal["white", "black"] | None
    uci: str | None

    @classmethod
    def of(cls, ref: MasterGameRef) -> "MasterGameRefOut":
        return cls(
            id=ref.id,
            white=ref.white,
            black=ref.black,
            white_rating=ref.white_rating,
            black_rating=ref.black_rating,
            year=ref.year,
            winner=ref.winner,
            uci=ref.uci,
        )


class ExplorerPositionOut(BaseModel):
    source: ExplorerSource
    white: int
    draws: int
    black: int
    games: int
    moves: list[ExplorerMoveOut]
    top_games: list[MasterGameRefOut]
    opening_eco: str | None
    opening_name: str | None

    @classmethod
    def of(cls, position: ExplorerPosition) -> "ExplorerPositionOut":
        return cls(
            source=position.source,
            white=position.white,
            draws=position.draws,
            black=position.black,
            games=position.games,
            moves=[ExplorerMoveOut.of(m) for m in position.moves],
            top_games=[MasterGameRefOut.of(g) for g in position.top_games],
            opening_eco=position.opening_eco,
            opening_name=position.opening_name,
        )


class MasterGameOut(BaseModel):
    id: str
    pgn: str
    white: str
    black: str
    white_rating: int | None
    black_rating: int | None
    year: int | None
    result: str

    @classmethod
    def of(cls, game: MasterGamePgn) -> "MasterGameOut":
        return cls(
            id=game.id,
            pgn=game.pgn,
            white=game.white,
            black=game.black,
            white_rating=game.white_rating,
            black_rating=game.black_rating,
            year=game.year,
            result=game.result,
        )


def get_explorer(request: Request) -> OpeningExplorer:
    explorer: OpeningExplorer = request.app.state.explorer
    return explorer


ExplorerDep = Annotated[OpeningExplorer, Depends(get_explorer)]


def _unavailable(exc: ExplorerUnavailableError) -> ApiError:
    return ApiError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        ErrorCode.EXPLORER_UNAVAILABLE,
        f"Lichess Explorer недоступен: {exc}",
    )


@router.get("/explorer", dependencies=[limit_user("explore")])
async def explorer_position(
    explorer: ExplorerDep,
    user: CurrentUser,
    fen: Annotated[str, Query(max_length=200)],
    source: ExplorerSource = ExplorerSource.MASTERS,
) -> ExplorerPositionOut:
    """Ходы из позиции с числом партий и результатами; у мастеров — ещё лучшие партии."""
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_FEN, "Некорректный FEN"
        ) from exc
    if not board.is_valid():
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_FEN, "Невозможная позиция"
        )
    try:
        return ExplorerPositionOut.of(await explorer.position(board, source=source))
    except ExplorerUnavailableError as exc:
        raise _unavailable(exc) from exc


@router.get("/explorer/games/{game_id}", dependencies=[limit_user("explore")])
async def explorer_game(
    explorer: ExplorerDep,
    user: CurrentUser,
    game_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9]{8}$")],
) -> MasterGameOut:
    """PGN партии мастеров и её данные (id — из `top_games`)."""
    try:
        return MasterGameOut.of(await explorer.master_game(game_id))
    except ExplorerUnavailableError as exc:
        raise _unavailable(exc) from exc
