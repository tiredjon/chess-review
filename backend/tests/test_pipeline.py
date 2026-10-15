"""Pipeline разбора и сериализация результата для БД — без движка, на заданных оценках."""

from collections.abc import Sequence

import chess
import pytest
from chess.engine import Cp, Mate, Score

from app.engine.analyzer import Analyzer
from app.review.evaluate import replay, terminal_eval
from app.review.motifs.base import Motif, MotifType
from app.review.pipeline import analyse_game, review_game
from app.review.types import EngineLine, MoveClass, Phase, PositionEval
from app.workers.serialize import accuracy_fields, line_json, motif_json, move_row
from tests.test_analyzer import FakeEngine

# Детский мат: 3… Nf6?? позволяет 4. Qxf7#.
SCHOLAR = ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]
# Оценки позиций за сторону на ходу; перед 3… Nf6 у чёрных ещё всё в порядке.
SCHOLAR_SCORES: list[Score] = [Cp(30), Cp(-30), Cp(20), Cp(-40), Cp(40), Cp(-60), Mate(1)]


def scripted_evals(
    start: chess.Board, moves: Sequence[chess.Move], scores: Sequence[Score]
) -> list[PositionEval]:
    """Оценки, где лучшая линия — продолжение партии (сыгранные ходы — лучшие)."""
    evals = []
    for index, board in enumerate(replay(start, moves)):
        terminal = terminal_eval(board)
        if terminal is not None:
            evals.append(terminal)
            continue
        line = EngineLine(score=scores[index], pv=tuple(moves[index : index + 4]))
        evals.append(PositionEval(score=line.score, lines=(line,), depth=10))
    return evals


@pytest.fixture
def scholar() -> list[chess.Move]:
    return [chess.Move.from_uci(uci) for uci in SCHOLAR]


def test_review_game_combines_classes_motifs_and_opening(scholar: list[chess.Move]) -> None:
    start = chess.Board()
    # Ход 3… Nf6 — не лучший: движок за чёрных предлагал 3… g6.
    evals = scripted_evals(start, scholar, SCHOLAR_SCORES)
    best_g6 = EngineLine(score=Cp(-60), pv=(chess.Move.from_uci("g7g6"),))
    evals[5] = PositionEval(score=best_g6.score, lines=(best_g6,), depth=10)

    review = review_game(start, scholar, evals)

    assert [m.eval.san for m in review.moves] == ["e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7#"]
    classes = [m.classification.move_class for m in review.moves]
    assert classes[0] == MoveClass.BOOK
    assert classes[5] == MoveClass.BLUNDER
    assert classes[6] == MoveClass.BEST
    assert {m.type for m in review.moves[6].motifs.played} >= {MotifType.MATE_IN_N}
    # Зевок наказывается матом.
    assert MotifType.MATE_IN_N in {m.type for m in review.moves[5].motifs.refutation}
    assert review.opening is not None
    assert review.opening.eco.startswith("C")
    white, black = review.accuracy[chess.WHITE], review.accuracy[chess.BLACK]
    assert white is not None
    assert black is not None
    assert white > black
    assert set(review.phase_accuracy[chess.WHITE]) == set(Phase)


async def test_analyse_game_uses_analyser_and_reports_progress() -> None:
    engine = FakeEngine()
    moves = [chess.Move.from_uci(uci) for uci in ("e2e4", "e7e5", "g1f3")]
    progress: list[tuple[int, int]] = []

    review = await analyse_game(
        Analyzer(engine),
        chess.Board(),
        moves,
        depth=5,
        multipv=2,
        on_progress=lambda done, total: progress.append((done, total)),
    )

    assert len(review.moves) == 3
    assert progress[-1] == (4, 4)
    assert len(engine.calls) >= 4


def test_move_row_for_blunder_and_mate(scholar: list[chess.Move]) -> None:
    review = review_game(
        chess.Board(), scholar, scripted_evals(chess.Board(), scholar, SCHOLAR_SCORES)
    )
    blunder, mate = move_row(review.moves[5]), move_row(review.moves[6])

    assert mate["san"] == "Qxf7#"
    assert mate["uci"] == "h5f7"
    assert (mate["eval_before_cp"], mate["mate_before"]) == (None, 1)
    # После хода, ставящего мат: mate_after == 0.
    assert (mate["eval_after_cp"], mate["mate_after"]) == (None, 0)
    assert mate["best_san"] == "Qxf7#"
    assert mate["pv"] == [{"uci": "h5f7", "san": "Qxf7#"}]
    assert mate["multipv"] == [{"cp": None, "mate": 1, "pv": [{"uci": "h5f7", "san": "Qxf7#"}]}]
    # Финальная позиция без движка: ответа нет.
    assert mate["reply_pv"] is None
    assert mate["win_after"] == pytest.approx(100.0, abs=3)

    assert blunder["eval_before_cp"] == -60
    assert (blunder["eval_after_cp"], blunder["mate_after"]) == (None, -1)
    assert blunder["reply_pv"] == [{"uci": "h5f7", "san": "Qxf7#"}]
    refutation = blunder["motifs"]["refutation"]
    mate_motif = next(m for m in refutation if m["type"] == "mate_in_n")
    assert mate_motif["line"][0] == {"uci": "h5f7", "san": "Qxf7#"}
    assert mate_motif["pieces"][0] == "Q"
    assert blunder["motifs"]["sacrifice"] is None
    assert blunder["phase"] == Phase.OPENING


def test_accuracy_fields(scholar: list[chess.Move]) -> None:
    review = review_game(
        chess.Board(), scholar, scripted_evals(chess.Board(), scholar, SCHOLAR_SCORES)
    )

    fields = accuracy_fields(review)

    assert fields["white_accuracy"] == review.accuracy[chess.WHITE]
    assert set(fields["phase_accuracy"]) == {"white", "black"}
    assert set(fields["phase_accuracy"]["black"]) == {"opening", "middlegame", "endgame"}


def test_line_json_handles_null_move_and_stops_at_illegal() -> None:
    board = chess.Board()
    line = [chess.Move.from_uci("e2e4"), chess.Move.null(), chess.Move.from_uci("d2d4")]
    illegal = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e2e4")]

    assert line_json(board, line) == [
        {"uci": "e2e4", "san": "e4"},
        {"uci": "0000", "san": "--"},
        {"uci": "d2d4", "san": "d4"},
    ]
    assert line_json(board, illegal) == [{"uci": "e2e4", "san": "e4"}]


def test_motif_json_names_squares_and_pieces() -> None:
    board = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
    motif = Motif(
        type=MotifType.MATE_THREAT,
        squares=(chess.A1, chess.E8),
        pieces=(chess.Piece(chess.ROOK, chess.WHITE), chess.Piece(chess.KING, chess.BLACK)),
        gain_cp=None,
        line=(chess.Move.from_uci("a1a7"), chess.Move.null()),
    )

    assert motif_json(board, motif) == {
        "type": "mate_threat",
        "squares": ["a1", "e8"],
        "pieces": ["R", "k"],
        "gain_cp": None,
        "line": [{"uci": "a1a7", "san": "Ra7"}, {"uci": "0000", "san": "--"}],
    }
