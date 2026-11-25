"""Сборка маленького курса против настоящего Lichess Masters. Ходит в сеть — только с
NETWORK_TESTS=1; движок — фейк (Stockfish проверяется ручной сборкой `python -m app.courses`)."""

import os

import chess
import pytest

from app.core.config import Settings
from app.courses.builder import BuildLimits, CourseBuilder, parse_line
from app.explorer.client import LichessExplorer
from app.importers.http import make_http_client
from tests.course_fakes import ROSSOLIMO, FakeEngine

pytestmark = pytest.mark.skipif(
    os.environ.get("NETWORK_TESTS") != "1", reason="сетевые тесты: NETWORK_TESTS=1"
)


async def test_rossolimo_live() -> None:
    settings = Settings()
    async with make_http_client(settings) as http:
        explorer = LichessExplorer.from_settings(settings, http)
        builder = CourseBuilder(
            explorer, FakeEngine(), limits=BuildLimits(target_plies=9, max_nodes=12)
        )
        tree = await builder.build(parse_line(ROSSOLIMO.split()), chess.WHITE)

    end = tree.nodes[tree.line_end]
    replies = [tree.nodes[i] for i in end.children]
    # После 3. Bb5 у мастеров чаще всего 3… g6, 3… e6, 3… d6.
    assert {r.san for r in replies} <= {"g6", "e6", "d6", "Nf6"}
    assert replies[0].stats is not None
    assert replies[0].stats.games > 1000
    assert tree.model_games
