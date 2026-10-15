import chess.engine


async def stockfish_version(path: str) -> str:
    """Запускает движок по UCI и возвращает его имя, например «Stockfish 19»."""
    _, engine = await chess.engine.popen_uci(path)
    try:
        return engine.id.get("name", "unknown")
    finally:
        await engine.quit()
