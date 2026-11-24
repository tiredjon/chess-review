"""Настоящий Lichess Opening Explorer. Ходит в сеть — только с NETWORK_TESTS=1.

База `lichess` без токена отвечает 401, поэтому живой тест — по базе мастеров."""

import os

import chess
import pytest

from app.core.config import Settings
from app.explorer.client import LichessExplorer
from app.importers.http import make_http_client

pytestmark = pytest.mark.skipif(
    os.environ.get("NETWORK_TESTS") != "1", reason="сетевые тесты: NETWORK_TESTS=1"
)


async def test_masters_live() -> None:
    settings = Settings()
    async with make_http_client(settings) as http:
        explorer = LichessExplorer.from_settings(settings, http)
        board = chess.Board()
        board.push_san("e4")
        position = await explorer.position(board)
        assert position.games > 100_000
        assert {m.san for m in position.moves} >= {"c5", "e5"}
        assert position.top_games

        game = await explorer.master_game(position.top_games[0].id)
        assert game.white
        assert game.pgn.count("1.") >= 1
