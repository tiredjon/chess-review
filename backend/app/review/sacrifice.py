"""Детектор жертвы (SPEC §4.5) — условие для `brilliant`.

Ход — жертва, если после него фигура ходящего (не пешка и не король) стоит под
боем без адекватной защиты — соперник выигрывает её взятием по SEE, — и в PV1
материал ходящего временно падает хотя бы на `SACRIFICE_MIN_MATERIAL_DROP` пешек
относительно позиции до хода. «Держится ли оценка» проверяет классификатор.

Уточнения, чтобы жертвой не считалось лишнее:
- Фигура, которая висела ещё до последнего хода соперника (он мог её взять, но
  не взял), — не новая жертва: её отдали раньше. Считаются фигуры, попавшие под
  бой этим ходом, и те, что игрок оставил под только что созданной угрозой.
- Потеря материала связана с самой жертвой: соперник берёт отданную фигуру
  в первые `SACRIFICE_ACCEPT_MOVES` своих ходов PV1, а материал считается после
  размена на этом поле. Иначе ход получал бы чужую жертву, сыгранную дальше в PV.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

import chess

from app.review.material import best_capture_gain, material_balance
from app.review.thresholds import SACRIFICE_ACCEPT_MOVES, SACRIFICE_MIN_MATERIAL_DROP


@dataclass(frozen=True, slots=True)
class Sacrifice:
    # Отданные фигуры: поля, на которых соперник их взял.
    squares: tuple[chess.Square, ...]
    # Наибольшая временная потеря материала в PV1, в пешках (> 0).
    material_drop: int


def en_prise(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    """Фигуры `color` (кроме пешек и короля), которые сторона на ходу выигрывает взятием."""
    pieces = board.occupied_co[color] & ~board.pawns & ~board.kings
    return [square for square in chess.SquareSet(pieces) if best_capture_gain(board, square) > 0]


def offered_pieces(
    board: chess.Board, move: chess.Move, prior: chess.Board | None = None
) -> list[chess.Square]:
    """Фигуры ходящего под боем после хода, кроме висевших ещё до хода соперника.

    `prior` — позиция до последнего хода соперника (None — неизвестна).
    """
    mover = board.turn
    after = board.copy(stack=False)
    after.push(move)
    squares = en_prise(after, mover)
    if prior is None or not squares:
        return squares
    stale = set(en_prise(prior, mover))
    return [
        square
        for square in squares
        if square not in stale or prior.piece_at(square) != after.piece_at(square)
    ]


def accepted_drops(
    board: chess.Board,
    move: chess.Move,
    pv: Sequence[chess.Move],
    offered: Collection[chess.Square],
) -> dict[chess.Square, int]:
    """Поле взятой соперником отданной фигуры → потеря материала ходящего (в пешках)
    относительно позиции до хода, после размена на этом поле."""
    mover = board.turn
    baseline = material_balance(board, mover)
    line = board.copy(stack=False)
    line.push(move)
    targets = {square: line.piece_at(square) for square in offered}
    drops: dict[chess.Square, int] = {}
    index = 0
    while index < min(len(pv), 2 * SACRIFICE_ACCEPT_MOVES):
        reply = pv[index]
        if not line.is_legal(reply):
            break
        square = reply.to_square
        accepted = (
            line.turn != mover and square in targets and targets[square] == line.piece_at(square)
        )
        line.push(reply)
        index += 1
        if not accepted:
            continue
        # Размен на поле жертвы доигрывается до конца, потом считается материал.
        while index < len(pv) and pv[index].to_square == square and line.is_legal(pv[index]):
            line.push(pv[index])
            index += 1
        drops[square] = baseline - material_balance(line, mover)
        del targets[square]
    return drops


def find_sacrifice(
    board: chess.Board,
    move: chess.Move,
    pv: Sequence[chess.Move],
    prior: chess.Board | None = None,
) -> Sacrifice | None:
    """`board` — позиция до хода, `pv` — лучшая линия после хода (первым ходит соперник),
    `prior` — позиция до последнего хода соперника (None — неизвестна)."""
    offered = offered_pieces(board, move, prior)
    if not offered:
        return None
    drops = {
        square: drop
        for square, drop in accepted_drops(board, move, pv, offered).items()
        if drop >= SACRIFICE_MIN_MATERIAL_DROP
    }
    if not drops:
        return None
    return Sacrifice(squares=tuple(drops), material_drop=max(drops.values()))
