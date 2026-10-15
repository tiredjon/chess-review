from app.engine.probe import stockfish_version


async def test_stockfish_is_installed(stockfish_path: str) -> None:
    version = await stockfish_version(stockfish_path)

    assert version.startswith("Stockfish")
