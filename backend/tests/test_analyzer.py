"""Analyzer на фейковом движке: кэш, финальные позиции, поиск альтернатив."""

from collections.abc import Collection

import chess
import pytest
from chess.engine import Cp, Mate

from app.engine.analyzer import Analyzer
from app.engine.cache import MemoryEvalCache, fen_key
from app.review.evaluate import replay
from app.review.types import EngineLine, PositionEval


class FakeEngine:
    """Ходы ранжирует по UCI; лучший получает +0.30, каждый следующий на 0.10 хуже."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, tuple[str, ...]]] = []

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        exclude: Collection[chess.Move] = (),
    ) -> PositionEval:
        self.calls.append((board.fen(), multipv, tuple(sorted(m.uci() for m in exclude))))
        moves = sorted((m for m in board.legal_moves if m not in exclude), key=lambda m: m.uci())
        lines = tuple(
            EngineLine(score=Cp(30 - 10 * rank), pv=(move,))
            for rank, move in enumerate(moves[:multipv])
        )
        return PositionEval(score=lines[0].score, lines=lines, depth=depth)


def best_of(board: chess.Board) -> chess.Move:
    return min(board.legal_moves, key=lambda m: m.uci())


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


async def test_terminal_positions_skip_engine(engine: FakeEngine) -> None:
    mated = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")

    result = await Analyzer(engine).analyse(mated, depth=10, multipv=3)

    assert result.score == Mate(0)
    assert engine.calls == []


async def test_single_line_when_played_move_is_not_best(engine: FakeEngine) -> None:
    board = chess.Board()
    played = chess.Move.from_uci("e2e4")
    assert played != best_of(board)

    result = await Analyzer(engine).analyse(board, depth=10, multipv=3, played={played})

    assert len(result.lines) == 1
    assert [multipv for _, multipv, _ in engine.calls] == [1]


async def test_alternatives_when_best_move_was_played(engine: FakeEngine) -> None:
    board = chess.Board()
    best = best_of(board)
    cache = MemoryEvalCache()

    result = await Analyzer(engine, cache).analyse(board, depth=10, multipv=3, played={best})

    assert result.best_move == best
    assert len(result.lines) == 3
    assert best not in [line.pv[0] for line in result.lines[1:]]
    assert [(mpv, excl) for _, mpv, excl in engine.calls] == [(1, ()), (2, (best.uci(),))]
    assert await cache.get(fen_key(board), 10, 1) is not None
    assert await cache.get(fen_key(board), 10, 3) == result


async def test_no_alternatives_for_multipv_one_or_forced_move(engine: FakeEngine) -> None:
    forced = chess.Board("7k/8/8/8/8/8/1r6/K7 w - - 0 1")  # единственный ход Kxb2
    assert forced.legal_moves.count() == 1
    analyzer = Analyzer(engine)

    await analyzer.analyse(chess.Board(), depth=5, multipv=1, played={best_of(chess.Board())})
    await analyzer.analyse(forced, depth=5, multipv=3, played={best_of(forced)})

    assert [multipv for _, multipv, _ in engine.calls] == [1, 1]


async def test_cache_hits_skip_engine(engine: FakeEngine) -> None:
    analyzer = Analyzer(engine, MemoryEvalCache())
    board = chess.Board()
    best = best_of(board)

    first = await analyzer.analyse(board, depth=10, multipv=3, played={best})
    calls = len(engine.calls)
    again = await analyzer.analyse(board, depth=10, multipv=3, played={best})
    single = await analyzer.analyse(board, depth=10, multipv=3)

    assert again == first
    assert len(single.lines) == 3  # полный набор из кэша уже есть
    assert len(engine.calls) == calls


async def test_analyse_game_dedupes_and_reports_progress(engine: FakeEngine) -> None:
    board = chess.Board()
    moves = [board.push_san(san) for san in ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3"]]
    positions = replay(chess.Board(), moves)
    progress: list[tuple[int, int]] = []

    evals = await Analyzer(engine).analyse_game(
        positions, moves, depth=5, multipv=1, on_progress=lambda d, t: progress.append((d, t))
    )

    # Стартовая позиция и позиция после Nf3 повторяются: 6 позиций, 4 уникальных.
    assert len(evals) == 6
    assert evals[0] is evals[4]
    assert evals[1] is evals[5]
    assert len(engine.calls) == 4
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]


async def test_analyse_game_handles_final_position(engine: FakeEngine) -> None:
    board = chess.Board()
    moves = [board.push_san(san) for san in ["f3", "e5", "g4", "Qh4#"]]

    evals = await Analyzer(engine).analyse_game(
        replay(chess.Board(), moves), moves, depth=5, multipv=1
    )

    assert evals[-1].score == Mate(0)
    assert len(engine.calls) == 4


async def test_analyse_game_validates_lengths(engine: FakeEngine) -> None:
    with pytest.raises(ValueError, match="на одну больше"):
        await Analyzer(engine).analyse_game(
            [chess.Board()], [chess.Move.null()], depth=1, multipv=1
        )
