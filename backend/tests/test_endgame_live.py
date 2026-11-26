"""Настоящий Lichess tablebase. Ходит в сеть — только с NETWORK_TESTS=1.

Сверяет цели каталога с живыми таблицами (то же, что фикстура, но без неё)."""

import os

import chess
import pytest

from app.core.config import Settings
from app.endgames.catalog import CATALOG
from app.endgames.tablebase import LichessTablebase
from app.importers.http import make_http_client

pytestmark = pytest.mark.skipif(
    os.environ.get("NETWORK_TESTS") != "1", reason="сетевые тесты: NETWORK_TESTS=1"
)


async def test_catalog_goals_live() -> None:
    settings = Settings()
    async with make_http_client(settings) as http:
        tablebase = LichessTablebase.from_settings(settings, http)
        for position in CATALOG:
            answer = await tablebase.probe(chess.Board(position.fen))
            assert answer.category == position.goal, position.id
            assert answer.moves[0].category == position.goal, position.id
