import chess
import pytest
from chess.engine import Cp, Mate, MateGiven

from app.review.accuracy import move_accuracy
from app.review.evaluate import evaluate_game, replay, terminal_eval
from app.review.types import EngineLine, Phase, PositionEval
from app.review.winprob import win_percent


def moves_of(sans: str, start: chess.Board | None = None) -> list[chess.Move]:
    board = (start or chess.Board()).copy()
    return [board.push_san(san) for san in sans.split()]


def pe(score: Cp | Mate, *pv: str) -> PositionEval:
    line = EngineLine(score=score, pv=tuple(chess.Move.from_uci(u) for u in pv))
    return PositionEval(score=score, lines=(line,), depth=10)


def test_terminal_eval() -> None:
    mated = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    stalemate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    bare_kings = chess.Board("8/8/4k3/8/8/4K3/8/8 w - - 0 1")

    assert terminal_eval(chess.Board()) is None
    assert terminal_eval(mated) == PositionEval(score=Mate(0))
    assert terminal_eval(stalemate) == PositionEval(score=Cp(0))
    assert terminal_eval(bare_kings) == PositionEval(score=Cp(0))


def test_replay_returns_all_positions_with_history() -> None:
    positions = replay(chess.Board(), moves_of("e4 e5 Nf3"))

    assert len(positions) == 4
    assert positions[0] == chess.Board()
    assert positions[3].move_stack == moves_of("e4 e5 Nf3")


def test_evals_are_normalized_to_the_mover() -> None:
    moves = moves_of("e4 e5")
    evals = [
        pe(Cp(20), "e2e4"),  # белые на ходу: +0.20
        pe(Cp(-50), "c7c5"),  # чёрные на ходу: для них −0.50, т.е. белые +0.50
        pe(Cp(300), "g1f3"),  # белые на ходу: +3.00
    ]

    white, black = evaluate_game(chess.Board(), moves, evals).moves

    assert (white.color, white.eval_before, white.eval_after) == (chess.WHITE, Cp(20), Cp(50))
    assert (black.color, black.eval_before, black.eval_after) == (chess.BLACK, Cp(-50), Cp(-300))
    assert white.win_before == pytest.approx(win_percent(Cp(20)))
    assert black.win_after == pytest.approx(100 - win_percent(Cp(300)))
    assert white.accuracy == 100.0
    assert black.accuracy < 50


def test_mates_are_scored_from_the_mover_side() -> None:
    moves = moves_of("f3 e5 g4 Qh4#")
    positions = replay(chess.Board(), moves)
    evals = [
        pe(Cp(20), "e2e4"),
        pe(Cp(30), "e7e5"),
        pe(Cp(-60), "e2e4"),
        pe(Mate(1), "d8h4"),
        terminal_eval(positions[-1]),
    ]
    assert evals[-1] is not None

    result = evaluate_game(chess.Board(), moves, [e for e in evals if e is not None])
    g4, mate = result.moves[2], result.moves[3]

    assert g4.eval_after == Mate(-1)
    assert g4.win_after == pytest.approx(win_percent(Cp(-1000)))
    assert g4.accuracy == move_accuracy(win_percent(Cp(-60)), win_percent(Cp(-1000)))
    assert mate.eval_before == Mate(1)
    assert mate.eval_after == MateGiven
    assert mate.accuracy == 100.0
    assert mate.san == "Qh4#"
    assert mate.best_move == chess.Move.from_uci("d8h4")


def test_move_fields() -> None:
    start = chess.Board("4k3/8/8/8/8/8/4P3/4K3 b - - 0 41")
    moves = moves_of("Kd7 e4", start)
    evals = [pe(Cp(-400)), pe(Cp(400), "e2e4"), pe(Cp(-450))]

    first, second = evaluate_game(start, moves, evals).moves

    assert (first.ply, first.fullmove, first.san, first.color) == (1, 41, "Kd7", chess.BLACK)
    assert (second.ply, second.fullmove, second.san) == (2, 42, "e4")
    assert first.fen_before == start.fen()
    assert first.phase is Phase.ENDGAME
    assert first.best_move is None
    assert second.best_move == chess.Move.from_uci("e2e4")
    assert second.lines == evals[1].lines
    assert first.lines_after == evals[1].lines
    assert second.lines_after == evals[2].lines


def test_game_and_phase_accuracy() -> None:
    moves = moves_of("e4 e5 Nf3 Nc6")
    evals = [pe(Cp(20)), pe(Cp(-20)), pe(Cp(400)), pe(Cp(-400)), pe(Cp(400))]

    result = evaluate_game(chess.Board(), moves, evals, book_plies=2)

    assert result.accuracy[chess.WHITE] == 100.0
    black = result.accuracy[chess.BLACK]
    assert black is not None
    assert black < 100.0
    assert [m.phase for m in result.moves] == [Phase.OPENING] * 3 + [Phase.MIDDLEGAME]
    assert result.phase_accuracy[chess.WHITE] == {
        Phase.OPENING: 100.0,
        Phase.MIDDLEGAME: None,
        Phase.ENDGAME: None,
    }
    assert result.phase_accuracy[chess.BLACK][Phase.MIDDLEGAME] == 100.0


def test_evaluate_game_requires_eval_per_position() -> None:
    with pytest.raises(ValueError, match="оценок"):
        evaluate_game(chess.Board(), moves_of("e4"), [pe(Cp(0))])


def test_empty_game() -> None:
    result = evaluate_game(chess.Board(), [], [pe(Cp(20))])

    assert result.moves == []
    assert result.accuracy == {chess.WHITE: None, chess.BLACK: None}
