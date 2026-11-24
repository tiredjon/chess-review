"""Признаки пешечной структуры (сессия 13): изолированные, сдвоенные, отсталые,
проходные и висячие пешки, острова, открытые линии, дыры, форпосты, большинство на
фланге, заблокированный центр, запертые цепи.

Горизонтали считаются «от себя»: `rel_rank` 1 — своя первая горизонталь, пешки стоят на
2–7. «Впереди» — ближе к стороне соперника. Признаки — только про пешки: где стоят
фигуры, решают уже идеи (`ideas.py`).
"""

from dataclasses import dataclass
from typing import Literal

import chess

Wing = Literal["queenside", "center", "kingside"]

# Зоны для пешечного большинства: ферзевый фланг a–c, центр d–e, королевский f–h.
# С тремя зонами атака меньшинства в Карлсбаде и большинство в сицилианской видны прямо.
WINGS: dict[Wing, tuple[int, ...]] = {
    "queenside": (0, 1, 2),
    "center": (3, 4),
    "kingside": (5, 6, 7),
}

# Дыры ищем на своей 3–4-й горизонтали по линиям c–f: дальше от центра они редко важны.
HOLE_RANKS = (3, 4)
HOLE_FILES = (2, 3, 4, 5)
# Форпост — на 5–6-й горизонтали (половина соперника) по линиям b–g: на краю коню тесно.
OUTPOST_RANKS = (5, 6)
OUTPOST_FILES = (1, 2, 3, 4, 5, 6)
# Висячие пешки — пара на своей 4-й горизонтали (c4/d4 у белых, c5/d5 у чёрных).
HANGING_RANK = 4


def rel_rank(color: chess.Color, square: chess.Square) -> int:
    """Горизонталь поля от стороны `color`: 1 — своя первая, 8 — первая соперника."""
    rank = chess.square_rank(square)
    return rank + 1 if color == chess.WHITE else 8 - rank


def square_at(color: chess.Color, file: int, rel: int) -> chess.Square:
    """Поле на вертикали `file` и горизонтали `rel` от стороны `color`."""
    return chess.square(file, rel - 1 if color == chess.WHITE else 8 - rel)


def ahead(color: chess.Color, square: chess.Square, steps: int = 1) -> chess.Square | None:
    """Поле на `steps` горизонталей впереди (по направлению хода пешек `color`)."""
    rel = rel_rank(color, square) + steps
    if not 1 <= rel <= 8:
        return None
    return square_at(color, chess.square_file(square), rel)


def is_dark(square: chess.Square) -> bool:
    return (chess.square_file(square) + chess.square_rank(square)) % 2 == 0


class PawnView:
    """Пешки одной стороны по вертикалям, горизонтали — от этой стороны."""

    def __init__(self, board: chess.Board, color: chess.Color) -> None:
        self.board = board
        self.color = color
        self.squares = tuple(sorted(board.pieces(chess.PAWN, color)))
        self._ranks: dict[int, list[int]] = {file: [] for file in range(8)}
        for square in self.squares:
            self._ranks[chess.square_file(square)].append(rel_rank(color, square))
        for ranks in self._ranks.values():
            ranks.sort()

    def ranks(self, file: int | str) -> list[int]:
        """Горизонтали (от себя) пешек на вертикали, по возрастанию."""
        return self._ranks[_file(file)]

    def has(self, file: int | str, *ranks: int) -> bool:
        """Есть ли пешка на вертикали (на одной из горизонталей `ranks`, если заданы)."""
        own = self.ranks(file)
        return bool(own) if not ranks else any(rank in ranks for rank in own)

    def none(self, file: int | str) -> bool:
        return not self.ranks(file)

    def square(self, file: int | str, rel: int) -> chess.Square:
        return square_at(self.color, _file(file), rel)

    def count(self, files: tuple[int, ...]) -> int:
        return sum(len(self._ranks[file]) for file in files)


def _file(file: int | str) -> int:
    return file if isinstance(file, int) else chess.FILE_NAMES.index(file)


def _adjacent(file: int) -> tuple[int, ...]:
    return tuple(f for f in (file - 1, file + 1) if 0 <= f <= 7)


def is_fixed(board: chess.Board, square: chess.Square) -> bool:
    """Пешка заблокирована пешкой соперника прямо перед ней."""
    pawn = board.piece_at(square)
    if pawn is None or pawn.piece_type != chess.PAWN:
        return False
    front = ahead(pawn.color, square)
    if front is None:
        return False
    blocker = board.piece_at(front)
    return blocker is not None and blocker.piece_type == chess.PAWN and blocker.color != pawn.color


def pawn_can_attack(board: chess.Board, color: chess.Color, square: chess.Square) -> bool:
    """Может ли пешка `color` атаковать поле сейчас или позже, продвигаясь по своей
    вертикали (путь не перекрыт пешками; взятия, меняющие вертикаль, не считаем)."""
    target, view = rel_rank(color, square), PawnView(board, color)
    for file in _adjacent(chess.square_file(square)):
        for rel in view.ranks(file):
            if rel >= target:
                continue
            path = (square_at(color, file, r) for r in range(rel + 1, target))
            if all(board.piece_type_at(s) != chess.PAWN for s in path):
                return True
    return False


@dataclass(frozen=True, slots=True)
class Chain:
    """Запертая цепь: пешки по диагонали, каждая заблокирована пешкой соперника.
    `squares` — от основания к голове."""

    color: chess.Color
    squares: tuple[chess.Square, ...]

    @property
    def base(self) -> chess.Square:
        return self.squares[0]

    @property
    def head(self) -> chess.Square:
        return self.squares[-1]

    @property
    def wing(self) -> Wing:
        """Куда направлена цепь: голова левее основания — на ферзевый фланг."""
        return (
            "queenside"
            if chess.square_file(self.head) < chess.square_file(self.base)
            else "kingside"
        )


@dataclass(frozen=True, slots=True)
class Majority:
    color: chess.Color
    wing: Wing
    own: int
    other: int


@dataclass(frozen=True, slots=True)
class SideFacts:
    """Признаки пешек одной стороны; все поля — по значимости / по вертикалям."""

    color: chess.Color
    isolated: tuple[chess.Square, ...]
    doubled: tuple[chess.Square, ...]
    backward: tuple[chess.Square, ...]
    passed: tuple[chess.Square, ...]
    hanging: tuple[chess.Square, ...]
    # Острова — группы соседних вертикалей с пешками.
    islands: tuple[tuple[int, ...], ...]
    half_open: tuple[int, ...]
    # Дыры этой стороны (её поля, которые пешкой уже не защитить).
    holes: tuple[chess.Square, ...]
    # Форпосты этой стороны (на половине соперника).
    outposts: tuple[chess.Square, ...]
    chains: tuple[Chain, ...]


@dataclass(frozen=True, slots=True)
class PawnFacts:
    white: SideFacts
    black: SideFacts
    open_files: tuple[int, ...]
    majorities: tuple[Majority, ...]
    blocked_center: bool

    def side(self, color: chess.Color) -> SideFacts:
        return self.white if color == chess.WHITE else self.black


def isolated(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    view = PawnView(board, color)
    return [s for s in view.squares if all(view.none(f) for f in _adjacent(chess.square_file(s)))]


def doubled(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    view = PawnView(board, color)
    return [s for s in view.squares if len(view.ranks(chess.square_file(s))) > 1]


def backward(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    """Отсталая: соседние пешки ушли вперёд (поддержать нечем), поле перед ней бьёт пешка
    соперника, а сама она на полуоткрытой для соперника линии. Изолированные — отдельно."""
    view, other = PawnView(board, color), PawnView(board, not color)
    result = []
    for square in view.squares:
        file, rel = chess.square_file(square), rel_rank(color, square)
        neighbours = [r for f in _adjacent(file) for r in view.ranks(f)]
        if not neighbours or any(r <= rel for r in neighbours):
            continue
        front = ahead(color, square)
        if front is None or not board.attackers_mask(not color, front) & board.pieces_mask(
            chess.PAWN, not color
        ):
            continue
        if any(9 - r > rel for r in other.ranks(file)):
            continue  # пешка соперника впереди на той же линии — линия не полуоткрыта
        result.append(square)
    return result


def passed(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    other = PawnView(board, not color)
    result = []
    for square in PawnView(board, color).squares:
        file, rel = chess.square_file(square), rel_rank(color, square)
        files = (file, *_adjacent(file))
        # Пешка соперника на горизонтали r (от него) стоит на нашей 9 − r.
        if not any(9 - r > rel for f in files for r in other.ranks(f)):
            result.append(square)
    return result


def hanging(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    """Висячие: пара на соседних вертикалях на своей 4-й горизонтали, сама по себе остров,
    а у соперника на этих вертикалях пешек нет."""
    view, other = PawnView(board, color), PawnView(board, not color)
    result: list[chess.Square] = []
    for island in islands(board, color):
        if len(island) != 2:
            continue
        if any(view.ranks(f) != [HANGING_RANK] or other.has(f) for f in island):
            continue
        result.extend(view.square(f, HANGING_RANK) for f in island)
    return result


def islands(board: chess.Board, color: chess.Color) -> list[tuple[int, ...]]:
    view = PawnView(board, color)
    groups: list[list[int]] = []
    for file in range(8):
        if view.none(file):
            continue
        if groups and groups[-1][-1] == file - 1:
            groups[-1].append(file)
        else:
            groups.append([file])
    return [tuple(group) for group in groups]


def open_files(board: chess.Board) -> list[int]:
    white, black = PawnView(board, chess.WHITE), PawnView(board, chess.BLACK)
    return [f for f in range(8) if white.none(f) and black.none(f)]


def half_open(board: chess.Board, color: chess.Color) -> list[int]:
    """Полуоткрытые линии `color`: своих пешек нет, у соперника есть."""
    own, other = PawnView(board, color), PawnView(board, not color)
    return [f for f in range(8) if own.none(f) and other.has(f)]


def holes(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    result = []
    for rel in HOLE_RANKS:
        for file in HOLE_FILES:
            square = square_at(color, file, rel)
            piece = board.piece_at(square)
            if piece is not None and piece.piece_type == chess.PAWN and piece.color == color:
                continue
            if not pawn_can_attack(board, color, square):
                result.append(square)
    return result


def outposts(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    own_pawns = board.pieces_mask(chess.PAWN, color)
    result = []
    for rel in OUTPOST_RANKS:
        for file in OUTPOST_FILES:
            square = square_at(color, file, rel)
            if board.piece_type_at(square) == chess.PAWN:
                continue
            if not board.attackers_mask(color, square) & own_pawns:
                continue
            if not pawn_can_attack(board, not color, square):
                result.append(square)
    return result


def chains(board: chess.Board, color: chess.Color) -> list[Chain]:
    """Запертые цепи длиной ≥ 2: каждая пешка заблокирована, задняя защищает переднюю."""
    fixed = {s for s in board.pieces(chess.PAWN, color) if is_fixed(board, s)}
    result = []
    for step in (-1, 1):
        for square in sorted(fixed, key=lambda s: rel_rank(color, s)):
            if _diagonal(color, square, step, back=True) in fixed:
                continue  # не основание
            run = [square]
            while (nxt := _diagonal(color, run[-1], step, back=False)) in fixed:
                run.append(nxt)
            if len(run) > 1:
                result.append(Chain(color, tuple(run)))
    return sorted(result, key=lambda chain: -len(chain.squares))


def _diagonal(
    color: chess.Color, square: chess.Square, step: int, *, back: bool
) -> chess.Square | None:
    file = chess.square_file(square) + (-step if back else step)
    rel = rel_rank(color, square) + (-1 if back else 1)
    if not (0 <= file <= 7 and 1 <= rel <= 8):
        return None
    return square_at(color, file, rel)


def majorities(board: chess.Board) -> list[Majority]:
    white, black = PawnView(board, chess.WHITE), PawnView(board, chess.BLACK)
    result = []
    for wing, files in WINGS.items():
        w, b = white.count(files), black.count(files)
        if w > b:
            result.append(Majority(chess.WHITE, wing, w, b))
        elif b > w:
            result.append(Majority(chess.BLACK, wing, b, w))
    return result


def blocked_center(board: chess.Board) -> bool:
    """На вертикалях d и e пешки белых упёрлись в пешки чёрных."""
    return all(
        any(
            is_fixed(board, s) and chess.square_file(s) == file
            for s in board.pieces(chess.PAWN, chess.WHITE)
        )
        for file in (3, 4)
    )


def side_facts(board: chess.Board, color: chess.Color) -> SideFacts:
    return SideFacts(
        color=color,
        isolated=tuple(isolated(board, color)),
        doubled=tuple(doubled(board, color)),
        backward=tuple(backward(board, color)),
        passed=tuple(passed(board, color)),
        hanging=tuple(hanging(board, color)),
        islands=tuple(islands(board, color)),
        half_open=tuple(half_open(board, color)),
        holes=tuple(holes(board, color)),
        outposts=tuple(outposts(board, color)),
        chains=tuple(chains(board, color)),
    )


def pawn_facts(board: chess.Board) -> PawnFacts:
    return PawnFacts(
        white=side_facts(board, chess.WHITE),
        black=side_facts(board, chess.BLACK),
        open_files=tuple(open_files(board)),
        majorities=tuple(majorities(board)),
        blocked_center=blocked_center(board),
    )
