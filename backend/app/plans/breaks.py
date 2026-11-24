"""Пешечные прорывы (сессия 13): ход пешкой, который бьёт пешку соперника или встаёт
на поле, откуда её атакует.

`legal_now` — ход легален и не теряет пешку на месте (SEE ≥ 0); для стороны не на ходу —
в той же позиции с передачей очереди (так у обеих сторон видно, что уже можно сыграть).
Иначе прорыв — цель подготовки: до поля один ход пешкой, но сейчас мешает фигура на пути
или пешку на этом поле просто заберут. Прорывы дальше одного хода (b2–b4–b5 в атаке
меньшинства) разбирают планы структур: общий поиск на два хода даёт в основном шум.
"""

from dataclasses import dataclass

import chess

from app.plans.pawns import PawnFacts, rel_rank, square_at
from app.plans.types import PawnBreak, Side
from app.review.material import see

MAX_BREAKS_PER_SIDE = 3
# Сколько ходов пешкой до поля прорыва (двойной ход с исходной — один ход).
MAX_PREPARE_MOVES = 1


def side_name(color: chess.Color) -> Side:
    return "white" if color == chess.WHITE else "black"


def as_mover(board: chess.Board, color: chess.Color) -> chess.Board | None:
    """Позиция, где ходит `color`. None — передать очередь нельзя (шах королю соперника)."""
    if board.turn == color:
        return board
    work = board.copy(stack=False)
    work.turn = color
    work.ep_square = None
    return work if work.is_valid() else None


@dataclass(frozen=True, slots=True)
class _Candidate:
    brk: PawnBreak
    score: int


def _target_score(target: chess.Square, bases: set[chess.Square]) -> int:
    file = chess.square_file(target)
    score = 30 if target in bases else 0
    if file in (3, 4):
        score += 15
    elif file in (2, 5):
        score += 10
    return score


def _push_destinations(
    board: chess.Board, color: chess.Color, square: chess.Square
) -> list[tuple[chess.Square, int]]:
    """Поля впереди пешки, куда она дойдёт за `MAX_PREPARE_MOVES` ходов по свободной от
    пешек вертикали: (поле, сколько ходов)."""
    file, rel = chess.square_file(square), rel_rank(color, square)
    result = []
    for dest_rel in range(rel + 1, 8):
        dest = square_at(color, file, dest_rel)
        if board.piece_type_at(dest) == chess.PAWN:
            break
        distance = dest_rel - rel
        moves = distance - 1 if rel == 2 and distance >= 2 else distance
        if moves > MAX_PREPARE_MOVES:
            break
        result.append((dest, moves))
    return result


def _best_target(targets: chess.SquareSet, bases: set[chess.Square]) -> chess.Square:
    return max(targets, key=lambda t: (_target_score(t, bases), -t))


def _side_breaks(board: chess.Board, facts: PawnFacts, color: chess.Color) -> list[_Candidate]:
    mover = as_mover(board, color)
    enemy = board.pieces(chess.PAWN, not color)
    bases = {chain.base for chain in facts.side(not color).chains}
    found: dict[tuple[chess.Square, chess.Square], _Candidate] = {}

    def add(square: chess.Square, dest: chess.Square, target: chess.Square, moves: int) -> None:
        move = chess.Move(square, dest)
        ready = moves == 1 and mover is not None and mover.is_legal(move) and see(mover, move) >= 0
        brk = PawnBreak(
            side=side_name(color),
            uci=move.uci(),
            san=mover.san(move) if ready and mover is not None else None,
            target=chess.square_name(target),
            legal_now=ready,
        )
        score = _target_score(target, bases) + (100 if ready else 0) - 5 * moves
        if (square, dest) not in found or found[(square, dest)].score < score:
            found[(square, dest)] = _Candidate(brk, score)

    for square in board.pieces(chess.PAWN, color):
        if rel_rank(color, square) >= 7:
            continue  # дальше — превращение, это не прорыв
        attacks = chess.SquareSet(chess.BB_PAWN_ATTACKS[color][square])
        for target in attacks & enemy:
            add(square, target, target, 1)
        for dest, moves in _push_destinations(board, color, square):
            if rel_rank(color, dest) == 8:
                continue
            hits = chess.SquareSet(chess.BB_PAWN_ATTACKS[color][dest]) & enemy
            if hits:
                add(square, dest, _best_target(hits, bases), moves)
    ranked = sorted(found.values(), key=lambda c: (-c.score, c.brk.uci))
    return ranked[:MAX_BREAKS_PER_SIDE]


def pawn_breaks(board: chess.Board, facts: PawnFacts) -> list[PawnBreak]:
    """Прорывы обеих сторон, самые значимые первыми (готовые — раньше подготовки)."""
    candidates = [c for color in chess.COLORS for c in _side_breaks(board, facts, color)]
    candidates.sort(key=lambda c: (-c.score, c.brk.side != "white", c.brk.uci))
    return [c.brk for c in candidates]
