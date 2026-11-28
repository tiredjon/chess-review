"""Описательная (английская) нотация старых книг → ход python-chess.

Ход вроде «Kt - K B 3», «Q R - Kt 1», «Kt (B 5) x Kt P», «P x P e.p.», «Castles» описан от
стороны, которая ходит: вертикали названы по фигурам начальной расстановки (QR — a,
QKt — b, QB — c, Q — d, K — e, KB — f, KKt — g, KR — h), горизонтали считаются от себя.
Неполное описание («B 4», «R x P») допустимо, если подходит ровно один легальный ход.

Фигуры с уточнением («K Kt», «Q R») — это фигуры по месту в начальной расстановке
(королевский конь — тот, что стоял на g1), поэтому `Tracker` помнит, откуда пришла каждая
лёгкая фигура и ладья. Пешка с уточнением («K B P») — пешка на этой вертикали сейчас.
"""

import re
from dataclasses import dataclass

import chess

_FILES = {"QR": 0, "QKt": 1, "QB": 2, "Q": 3, "K": 4, "KB": 5, "KKt": 6, "KR": 7}
# Вертикали без указания фланга: «B» — c или f.
_SIDELESS = {"R": (0, 7), "Kt": (1, 6), "B": (2, 5)}
_PIECES = {"P": chess.PAWN, "Kt": chess.KNIGHT, "B": chess.BISHOP, "R": chess.ROOK}
_PIECES |= {"Q": chess.QUEEN, "K": chess.KING}

# Фигура: необязательный фланг (K/Q), затем R/Kt/B; или K, Q, P.
_PIECE = r"(?:[KQ]?(?:R|Kt|B)P?|[KQ]P|K|Q|P)"
_SQUARE = r"(?:[KQ]?(?:R|Kt|B)|K|Q)[1-8]"
_MOVE = re.compile(
    rf"^(?P<piece>{_PIECE})"
    rf"(?:\((?P<origin>{_SQUARE})\))?"
    r"(?P<sep>[-x])"
    rf"(?P<target>{_SQUARE}|{_PIECE})"
    rf"(?:\((?P<at>{_SQUARE})\))?"
    r"(?:=?\(?(?P<promo>Q|R|B|Kt)\)?)?$"
)
_CASTLES = {"O-O": "K", "O-O-O": "Q", "Castles": None, "CastlesKR": "K", "CastlesQR": "Q"}
_CASTLES |= {"Castles(K)": "K", "Castles(Q)": "Q", "Castles(KR)": "K", "Castles(QR)": "Q"}
# Хвосты, не влияющие на выбор хода (шах проверяем отдельно).
_SUFFIX = re.compile(r"(?:dis\.?|double)?(?:ch\.?|mate|\+)$")
_EP = re.compile(r"e\.?p\.?$")
_NAGS = {"!!": 3, "??": 4, "!?": 5, "?!": 6, "!": 1, "?": 2}


class NotationError(ValueError):
    """Ход не разобран или подходит не ровно один легальный ход."""


@dataclass(frozen=True, slots=True)
class Parsed:
    move: chess.Move
    nag: int | None


def _clean(text: str) -> tuple[str, int | None, bool]:
    """Убрать пробелы и знаки оценки: «Kt x B ch !» → («KtxB», 1, шах)."""
    text = text.replace(" ", "").replace("X", "x").replace("×", "x").replace("–", "-")
    # Опечатки распознавания текста: «KT» вместо «Kt», «I»/«l» вместо «1».
    text = text.replace("KT", "Kt").replace("kt", "Kt")
    text = re.sub(r"(?<=[A-Za-z])[Il](?=$|ch|[!?.,;+])", "1", text)
    text = text.replace("sq", "1")  # «K-R sq» — старая запись первой горизонтали
    text = re.sub(r"^(\w+)-\((\w+)\)", r"\1(\2)-", text)  # «R-(B5)B7» → «R(B5)-B7»
    text = text.replace("O-O-O", "O-O-O").replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    nag = None
    for mark, code in _NAGS.items():
        if text.endswith(mark):
            text, nag = text[: -len(mark)], code
            break
    text = text.rstrip(".,;")
    text = re.sub(r"(?:Mate|Ch)$", lambda m: m.group(0).lower(), text)
    check = False
    if match := _SUFFIX.search(text):
        check = match.group(0) != ""
        text = text[: match.start()]
    text = _EP.sub("", text).rstrip(".,")
    for mark, code in _NAGS.items():  # «Q-R5ch!» — оценка после шаха
        if text.endswith(mark):
            text, nag = text[: -len(mark)], nag or code
            break
    return text, nag, check


def _files(name: str) -> tuple[int, ...]:
    if name in _FILES:
        return (_FILES[name],)
    return _SIDELESS[name]


def _squares(descr: str, color: chess.Color) -> set[chess.Square]:
    """«KB3» → {f3} для белых / {f6} для чёрных; «B4» → обе вертикали слона."""
    rank = int(descr[-1])
    rank_index = rank - 1 if color == chess.WHITE else 8 - rank
    return {chess.square(f, rank_index) for f in _files(descr[:-1])}


def _split_piece(name: str) -> tuple[int, str | None, str | None]:
    """«QKt» → (конь, фланг Q, None); «KBP» → (пешка, None, вертикаль KB); «P» → пешка."""
    if name.endswith("P") and name != "P":
        return chess.PAWN, None, name[:-1]
    if name in ("K", "Q", "P"):
        return _PIECES[name], None, None
    wing = name[0] if name[0] in "KQ" and len(name) > 1 and name[1:] in _PIECES else None
    return _PIECES[name[1:] if wing else name], wing, None


class Tracker:
    """Позиция партии и происхождение фигур: квадрат → вертикаль начальной расстановки."""

    def __init__(self, board: chess.Board | None = None) -> None:
        self.board = board or chess.Board()
        self.home: dict[chess.Square, int] = {
            sq: chess.square_file(sq)
            for sq in self.board.piece_map()
            if self.board.piece_type_at(sq) in (chess.ROOK, chess.KNIGHT, chess.BISHOP)
        }

    def _wing_ok(self, square: chess.Square, wing: str | None) -> bool:
        if wing is None:
            return True
        file = self.home.get(square, chess.square_file(square))
        return (file >= 4) == (wing == "K")

    def push(self, move: chess.Move) -> None:
        board = self.board
        if board.is_castling(move):
            rook_from, rook_to = (
                (chess.H1, chess.F1)
                if chess.square_file(move.to_square) == 6
                else (chess.A1, chess.D1)
            )
            if board.turn == chess.BLACK:
                rook_from, rook_to = chess.square_mirror(rook_from), chess.square_mirror(rook_to)
            if rook_from in self.home:
                self.home[rook_to] = self.home.pop(rook_from)
        self.home.pop(move.to_square, None)
        if move.from_square in self.home:
            self.home[move.to_square] = self.home.pop(move.from_square)
        board.push(move)

    def copy(self) -> "Tracker":
        other = Tracker.__new__(Tracker)
        other.board = self.board.copy(stack=False)
        other.home = dict(self.home)
        return other

    def parse(self, text: str) -> Parsed:
        moves, nag = self.candidates(text)
        return Parsed(self._one(moves, text), nag)

    def candidates(self, text: str) -> tuple[list[chess.Move], int | None]:
        """Все легальные ходы, подходящие под запись (после уточнений фланга и шаха).
        Запись «=SAN» — ход в алгебраической нотации (исправления опечаток книги)."""
        board = self.board
        if text.startswith("="):
            return [board.parse_san(text[1:])], None
        raw = text
        text, nag, check = _clean(text)
        if text in _CASTLES:
            return self._castles(_CASTLES[text]), nag
        match = _MOVE.match(text)
        if match is None and (bare := re.fullmatch(rf"({_PIECE})({_SQUARE})", text)):
            match = _MOVE.match(f"{bare.group(1)}-{bare.group(2)}")  # «P K 4» без дефиса
        if match is None:
            raise NotationError(f"не разобран ход {raw!r}")
        candidates = [m for m in board.legal_moves if self._fits(m, match)]
        if len(candidates) > 1:
            wing = _split_piece(match["piece"])[1]
            by_wing = [m for m in candidates if self._wing_ok(m.from_square, wing)]
            candidates = by_wing or candidates
        if len(candidates) > 1:
            # Книги отмечают шах («ch»): без пометки — ход без шаха, с пометкой — с шахом.
            marked = [m for m in candidates if board.gives_check(m) == check]
            candidates = marked or candidates
        return candidates, nag

    def _castles(self, side: str | None) -> list[chess.Move]:
        board = self.board
        moves = [m for m in board.legal_moves if board.is_castling(m)]
        if side is not None:
            moves = [m for m in moves if (chess.square_file(m.to_square) == 6) == (side == "K")]
        if len(moves) > 1:  # «Castles» без фланга: короткая, если обе возможны
            moves = [m for m in moves if chess.square_file(m.to_square) == 6]
        return moves

    def _fits(self, move: chess.Move, match: re.Match[str]) -> bool:
        """Ход подходит под запись без уточнения фланга фигуры: тип фигуры, взятие, поле
        или взятая фигура, вертикаль пешки, поле отправления, превращение."""
        board = self.board
        piece_type, _, pawn_file = _split_piece(match["piece"])
        capture = match["sep"] == "x"
        target, origin, promo = match["target"], match["origin"], match["promo"]
        if capture:
            lands = self._captures(move, target, match["at"])
        else:
            lands = bool(re.fullmatch(_SQUARE, target)) and move.to_square in _squares(
                target, board.turn
            )
        return (
            lands
            and board.piece_type_at(move.from_square) == piece_type
            and not board.is_castling(move)
            and board.is_capture(move) == capture
            and (pawn_file is None or chess.square_file(move.from_square) in _files(pawn_file))
            and (not origin or move.from_square in _squares(origin, board.turn))
            and move.promotion == (_PIECES[promo] if promo else None)
        )

    def _captures(self, move: chess.Move, target: str, at: str | None) -> bool:
        board = self.board
        victim = chess.PAWN if board.is_en_passant(move) else board.piece_type_at(move.to_square)
        if re.fullmatch(_SQUARE, target):
            return move.to_square in _squares(target, board.turn)
        kind, wing, pawn_file = _split_piece(target)
        if victim != kind:
            return False
        if at and move.to_square not in _squares(at, board.turn):
            return False
        square = move.to_square
        if board.is_en_passant(move):
            square = chess.square(
                chess.square_file(move.to_square), chess.square_rank(move.from_square)
            )
        if pawn_file is not None:
            return chess.square_file(square) in _files(pawn_file)
        return self._wing_ok(square, wing)

    def _one(self, moves: list[chess.Move], raw: str) -> chess.Move:
        if len(moves) == 1:
            return moves[0]
        if not moves:
            raise NotationError(f"нет легального хода {raw!r} в {self.board.fen()}")
        sans = ", ".join(self.board.san(m) for m in moves)
        raise NotationError(f"неоднозначно {raw!r}: {sans} в {self.board.fen()}")


def looks_like_move(text: str) -> bool:
    """Похоже ли на запись хода (для разметки строк книги, без проверки легальности)."""
    clean, _, _ = _clean(text)
    return (
        clean in _CASTLES
        or _MOVE.match(clean) is not None
        or re.fullmatch(rf"{_PIECE}{_SQUARE}", clean) is not None
    )
