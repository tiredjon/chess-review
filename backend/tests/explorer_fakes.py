"""Фейк Opening Explorer для тестов кэша и API."""

import json
from pathlib import Path

import chess

from app.explorer.client import parse_master_pgn, parse_position
from app.explorer.types import (
    ExplorerPosition,
    ExplorerSource,
    ExplorerUnavailableError,
    MasterGamePgn,
)

DATA = Path(__file__).parent / "data" / "explorer"


class FakeExplorer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.position_calls: list[tuple[str, ExplorerSource]] = []
        self.game_calls: list[str] = []

    async def position(
        self, board: chess.Board, *, source: ExplorerSource = ExplorerSource.MASTERS
    ) -> ExplorerPosition:
        self.position_calls.append((board.epd(), source))
        if self.fail:
            raise ExplorerUnavailableError("тест")
        name = "masters_e4.json" if source is ExplorerSource.MASTERS else "lichess_e4.json"
        return parse_position(source, json.loads((DATA / name).read_text()))

    async def master_game(self, game_id: str) -> MasterGamePgn:
        self.game_calls.append(game_id)
        if self.fail:
            raise ExplorerUnavailableError("тест")
        return parse_master_pgn(game_id, (DATA / "master_game.pgn").read_text())
