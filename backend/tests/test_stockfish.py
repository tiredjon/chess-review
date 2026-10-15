import os
import shutil

import pytest

from app.core.config import Settings
from app.engine.probe import stockfish_version


async def test_stockfish_is_installed(settings: Settings) -> None:
    """В Docker-образе (REQUIRE_STOCKFISH=1) движок обязан быть; локально — по возможности."""
    if shutil.which(settings.stockfish_path) is None:
        if os.environ.get("REQUIRE_STOCKFISH") == "1":
            pytest.fail(f"Stockfish не найден: {settings.stockfish_path}")
        pytest.skip("Stockfish не установлен локально (brew install stockfish)")

    version = await stockfish_version(settings.stockfish_path)

    assert version.startswith("Stockfish")
