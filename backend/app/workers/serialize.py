"""Разбор партии (`GameReview`) → поля строк `analyses` / `moves` и их JSON.

Формат JSON-полей хода:
- линия (`pv`, `reply_pv`, `line` мотива) — `[{"uci": "e2e4", "san": "e4"}, ...]`;
  нулевой ход («любой ход соперника» в угрозах) — `{"uci": "0000", "san": "--"}`;
- `multipv` — `[{"cp": 35, "mate": null, "pv": <линия>}, ...]`, оценки — за ходящего;
- `motifs` — `{"played": [...], "missed": [...], "refutation": [...], "sacrifice": ...}`,
  мотив — `{"type", "squares": ["e7", ...], "pieces": ["N", "k", ...], "gain_cp", "line"}`
  (регистр фигуры — цвет, как в FEN).
"""

from collections.abc import Sequence
from typing import Any

import chess
from chess.engine import Score

from app.review.motifs.base import Motif
from app.review.motifs.context import MoveMotifs
from app.review.pipeline import GameReview, MoveReview
from app.review.sacrifice import Sacrifice
from app.review.types import EngineLine

COLOR_NAMES = {chess.WHITE: "white", chess.BLACK: "black"}


def split_score(score: Score) -> tuple[int | None, int | None]:
    """(cp, mate). `mate == 0` после хода — ходящий поставил мат."""
    mate = score.mate()
    return (score.score(), None) if mate is None else (None, mate)


def line_json(board: chess.Board, moves: Sequence[chess.Move]) -> list[dict[str, str]]:
    """Линия из позиции `board`; обрывается на первом нелегальном ходе."""
    work = board.copy(stack=False)
    result = []
    for move in moves:
        if move and not work.is_legal(move):
            break
        result.append({"uci": move.uci(), "san": work.san(move)})
        work.push(move)
    return result


def engine_line_json(board: chess.Board, line: EngineLine) -> dict[str, Any]:
    cp, mate = split_score(line.score)
    return {"cp": cp, "mate": mate, "pv": line_json(board, line.pv)}


def motif_json(board: chess.Board, motif: Motif) -> dict[str, Any]:
    return {
        "type": motif.type.value,
        "squares": [chess.square_name(square) for square in motif.squares],
        "pieces": [piece.symbol() for piece in motif.pieces],
        "gain_cp": motif.gain_cp,
        "line": line_json(board, motif.line),
    }


def sacrifice_json(sacrifice: Sacrifice | None) -> dict[str, Any] | None:
    if sacrifice is None:
        return None
    return {
        "squares": [chess.square_name(square) for square in sacrifice.squares],
        "material_drop": sacrifice.material_drop,
    }


def motifs_json(
    before: chess.Board, after: chess.Board, motifs: MoveMotifs, sacrifice: Sacrifice | None
) -> dict[str, Any]:
    return {
        "played": [motif_json(before, motif) for motif in motifs.played],
        "missed": [motif_json(before, motif) for motif in motifs.missed],
        "refutation": [motif_json(after, motif) for motif in motifs.refutation],
        "sacrifice": sacrifice_json(sacrifice),
    }


def move_row(review: MoveReview) -> dict[str, Any]:
    """Поля строки `moves` (без analysis_id)."""
    move = review.eval
    before = chess.Board(move.fen_before)
    after = before.copy(stack=False)
    after.push(move.move)
    eval_before_cp, mate_before = split_score(move.eval_before)
    eval_after_cp, mate_after = split_score(move.eval_after)
    best = move.best_move
    return {
        "ply": move.ply,
        "san": move.san,
        "uci": move.move.uci(),
        "fen_before": move.fen_before,
        "eval_before_cp": eval_before_cp,
        "eval_after_cp": eval_after_cp,
        "mate_before": mate_before,
        "mate_after": mate_after,
        "win_before": move.win_before,
        "win_after": move.win_after,
        "accuracy": move.accuracy,
        "move_class": review.classification.move_class,
        "is_miss": review.classification.is_miss,
        "best_uci": best.uci() if best else None,
        "best_san": before.san(best) if best else None,
        "pv": line_json(before, move.lines[0].pv) if move.lines else None,
        "multipv": [engine_line_json(before, line) for line in move.lines],
        "reply_pv": line_json(after, move.lines_after[0].pv) if move.lines_after else None,
        "motifs": motifs_json(before, after, review.motifs, review.classification.sacrifice),
        "phase": move.phase,
    }


def accuracy_fields(review: GameReview) -> dict[str, Any]:
    """Поля строки `analyses` с точностью: общей и по фазам (`{"white": {"opening": …}}`)."""
    return {
        "white_accuracy": review.accuracy[chess.WHITE],
        "black_accuracy": review.accuracy[chess.BLACK],
        "phase_accuracy": {
            COLOR_NAMES[color]: {phase.value: value for phase, value in phases.items()}
            for color, phases in review.phase_accuracy.items()
        },
    }
