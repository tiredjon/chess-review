"""Мотивы хода в трёх контекстах: сам ход, упущенный PV1, наказание (ответ соперника)."""

from collections.abc import Sequence

import chess
from chess.engine import Cp, Score

from app.review.evaluate import MoveEval, evaluate_game
from app.review.motifs.base import Motif, MotifType
from app.review.motifs.context import game_motifs, move_motifs
from app.review.types import EngineLine, PositionEval


def pe(score: Score, *pv: str) -> PositionEval:
    line = EngineLine(score=score, pv=tuple(chess.Move.from_uci(m) for m in pv))
    return PositionEval(score=score, lines=(line,) if pv else (), depth=18)


def single(fen: str, move: str, before: PositionEval, after: PositionEval) -> MoveEval:
    (result,) = evaluate_game(chess.Board(fen), [chess.Move.from_uci(move)], [before, after]).moves
    return result


def types(motifs: Sequence[Motif]) -> list[MotifType]:
    return [m.type for m in motifs]


def test_missed_fork() -> None:
    # Белые играют Ke2, а Nc7+ с вилкой выигрывал ладью.
    move = single(
        "r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1",
        "e1e2",
        pe(Cp(500), "b5c7", "e8e7", "c7a8"),
        pe(Cp(0), "a8a5"),
    )
    motifs = move_motifs(move)
    assert motifs.played == ()
    assert types(motifs.missed) == [MotifType.FORK]
    assert motifs.missed[0].gain_cp == 500
    assert motifs.refutation == ()


def test_refutation_takes_hanging_piece() -> None:
    # Чёрные оставляют ладью c3 под конём: наказание — Nxc3.
    move = single(
        "4k3/8/8/8/8/2r5/8/1N2K3 b - - 0 1",
        "e8d7",
        pe(Cp(0), "c3c8"),
        pe(Cp(500), "b1c3"),
    )
    motifs = move_motifs(move)
    assert types(motifs.refutation) == [MotifType.HANGING_PIECE]
    assert motifs.refutation[0].squares == (chess.C3, chess.C3)
    assert motifs.missed == ()


def test_best_move_has_no_missed_and_terminal_has_no_refutation() -> None:
    move = single(
        "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1",
        "a1a8",
        pe(Cp(1000), "a1a8"),
        PositionEval(score=Cp(0)),
    )
    motifs = move_motifs(move)
    assert types(motifs.played) == [MotifType.MATE_IN_N, MotifType.BACK_RANK]
    assert (motifs.missed, motifs.refutation) == ((), ())


def test_game_motifs_use_history_for_recaptures() -> None:
    start = chess.Board("4k3/1p6/2n5/1B6/8/8/8/4K3 w - - 0 1")
    moves = [chess.Move.from_uci("b5c6"), chess.Move.from_uci("b7c6")]
    evals = [pe(Cp(0), "b5c6", "b7c6"), pe(Cp(-300), "b7c6"), pe(Cp(0), "e1e2")]
    result = evaluate_game(start, moves, evals).moves

    with_history = game_motifs(result)
    assert len(with_history) == 2
    # bxc6 — взятие в ответ на Bxc6, обычный размен.
    assert with_history[1].played == ()
    # Без истории то же взятие выглядит как взятие висящей фигуры.
    assert types(move_motifs(result[1]).played) == [MotifType.HANGING_PIECE]
