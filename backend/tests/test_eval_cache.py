import chess
import pytest
from chess.engine import Cp, Mate

from app.db.session import Database
from app.engine.cache import DbEvalCache, MemoryEvalCache, eval_from_data, eval_to_data, fen_key
from app.review.types import EngineLine, PositionEval


def sample_eval() -> PositionEval:
    lines = (
        EngineLine(score=Mate(3), pv=tuple(map(chess.Move.from_uci, ["d1d8", "f8e8", "d8e8"]))),
        EngineLine(score=Cp(-45), pv=(chess.Move.from_uci("e7e8q"),)),
    )
    return PositionEval(score=lines[0].score, lines=lines, depth=18)


def test_fen_key_ignores_move_counters() -> None:
    a = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    b = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 7 30")

    assert fen_key(a) == fen_key(b) == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -"


def test_fen_key_keeps_en_passant_only_when_capture_is_possible() -> None:
    no_capture = chess.Board()
    no_capture.push_san("e4")
    capture = chess.Board("rnbqkbnr/ppp1pppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3")
    capture.push_san("c4")

    assert fen_key(no_capture).endswith(" -")
    assert fen_key(capture).endswith(" c3")


def test_serialization_roundtrip() -> None:
    value = sample_eval()

    assert eval_from_data(eval_to_data(value)) == value
    assert eval_to_data(value)["lines"][1] == {"cp": -45, "pv": ["e7e8q"]}


def test_mate_on_board_is_not_serialized() -> None:
    with pytest.raises(ValueError, match="мат на доске"):
        eval_to_data(PositionEval(score=Mate(0), lines=(EngineLine(Mate(0), ()),)))


async def test_memory_cache() -> None:
    cache = MemoryEvalCache()

    await cache.put("k", 18, 3, sample_eval())

    assert await cache.get("k", 18, 3) == sample_eval()
    assert await cache.get("k", 18, 1) is None
    assert await cache.get("k", 16, 3) is None
    assert len(cache) == 1


@pytest.mark.integration
async def test_db_cache(migrated_db: str) -> None:
    db = Database(migrated_db)
    try:
        cache = DbEvalCache(db.sessionmaker)
        key = fen_key(chess.Board())

        assert await cache.get(key, 18, 3) is None
        await cache.put(key, 18, 3, sample_eval())
        # Повторная запись того же ключа не падает (гонка двух воркеров).
        await cache.put(key, 18, 3, sample_eval())

        assert await cache.get(key, 18, 3) == sample_eval()
        assert await cache.get(key, 18, 1) is None
    finally:
        await db.dispose()
