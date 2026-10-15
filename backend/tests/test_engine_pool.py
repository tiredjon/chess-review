"""Пул Stockfish на настоящем движке (без Stockfish тесты пропускаются)."""

import asyncio
import os
import signal
from collections.abc import AsyncIterator

import chess
import pytest
from chess.engine import Cp, Mate

from app.engine.pool import EngineError, EnginePool

MATE_IN_ONE = chess.Board("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1")  # Rd8#
BLACK_UP_A_QUEEN = "q5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1"


@pytest.fixture
async def pool(stockfish_path: str) -> AsyncIterator[EnginePool]:
    async with EnginePool(stockfish_path, 2, hash_mb=16, timeout=30) as p:
        yield p


async def test_analyse_returns_multipv_lines(pool: EnginePool) -> None:
    board = chess.Board()

    result = await pool.analyse(board, depth=10, multipv=3)

    assert pool.version.startswith("Stockfish")
    assert len(result.lines) == 3
    assert result.depth == 10
    assert result.score == result.lines[0].score
    assert result.best_move is not None
    assert board.is_legal(result.best_move)
    assert abs(result.score.score() or 0) < 100
    # Линии отсортированы от лучшей к худшей.
    scores = [line.score.score() or 0 for line in result.lines]
    assert scores == sorted(scores, reverse=True)


async def test_finds_mate_in_one(pool: EnginePool) -> None:
    result = await pool.analyse(MATE_IN_ONE, depth=8, multipv=1)

    assert result.score == Mate(1)
    assert result.best_move == chess.Move.from_uci("d1d8")


async def test_scores_are_from_side_to_move(pool: EnginePool) -> None:
    black_to_move = chess.Board(BLACK_UP_A_QUEEN)
    white_to_move = chess.Board(BLACK_UP_A_QUEEN.replace(" b ", " w "))

    for_black = await pool.analyse(black_to_move, depth=8, multipv=1)
    for_white = await pool.analyse(white_to_move, depth=8, multipv=1)

    assert for_black.score > Cp(500)
    assert for_white.score < Cp(-500)


async def test_exclude_skips_moves(pool: EnginePool) -> None:
    best = chess.Move.from_uci("d1d8")

    result = await pool.analyse(MATE_IN_ONE, depth=8, multipv=2, exclude=[best])

    assert all(line.pv[0] != best for line in result.lines)
    assert result.score != Mate(1)


async def test_multipv_is_capped_by_legal_moves(pool: EnginePool) -> None:
    board = chess.Board("7k/8/8/8/8/8/r7/K7 w - - 0 1")  # Kb1 и Kxa2
    assert board.legal_moves.count() == 2

    result = await pool.analyse(board, depth=8, multipv=5)

    assert len(result.lines) == 2


async def test_parallel_analyses_share_the_pool(pool: EnginePool) -> None:
    boards = [chess.Board(), MATE_IN_ONE, chess.Board(BLACK_UP_A_QUEEN)] * 2

    results = await asyncio.gather(*(pool.analyse(b, depth=6, multipv=1) for b in boards))

    assert len(results) == 6
    assert len(pool.pids) == 2


async def test_restarts_crashed_engine(stockfish_path: str) -> None:
    async with EnginePool(stockfish_path, 1, hash_mb=16) as pool:
        (pid,) = pool.pids
        os.kill(pid, signal.SIGKILL)
        await asyncio.sleep(0.1)

        result = await pool.analyse(MATE_IN_ONE, depth=6, multipv=1)

        assert result.score == Mate(1)
        assert pool.pids != [pid]


async def test_timeout_restarts_engine_and_raises(stockfish_path: str) -> None:
    async with EnginePool(stockfish_path, 1, hash_mb=16, timeout=0.05, retries=1) as pool:
        (pid,) = pool.pids

        with pytest.raises(EngineError):
            await pool.analyse(chess.Board(), depth=40, multipv=3)

        pool.timeout = 30
        result = await pool.analyse(MATE_IN_ONE, depth=6, multipv=1)

        assert result.score == Mate(1)
        assert pool.pids != [pid]


async def test_analyse_requires_started_pool(stockfish_path: str) -> None:
    pool = EnginePool(stockfish_path, 1)

    with pytest.raises(RuntimeError, match="не запущен"):
        await pool.analyse(chess.Board(), depth=1, multipv=1)


async def test_start_fails_for_missing_binary() -> None:
    with pytest.raises(FileNotFoundError):
        await EnginePool("/nonexistent/stockfish", 1).start()


def test_pool_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="size"):
        EnginePool("stockfish", 0)
