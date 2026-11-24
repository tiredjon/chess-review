"""Каталог типовых пешечных структур (сессия 13) и их распознавание по пешкам.

Правило структуры записано от лица её «владельца» (сторона с изолятором, с цепью e5,
с атакой меньшинства…) в горизонталях от себя, поэтому одно правило ловит структуру за
любой цвет: Каро-Канн с разменом — тот же Карлсбад, только владелец — чёрные. Исключения
названы по цвету и зеркально не ищутся: Лондон — система белых, славянская / Каро-Канн
(c6 + d5) — защита чёрных; та же расстановка за другой цвет — уже другие дебюты.

Порядок `CATALOG` — от самой точной структуры к общей: первая распознанная даёт
заголовок и описание.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

import chess

from app.plans.pawns import PawnView


class StructureId(StrEnum):
    HEDGEHOG = "hedgehog"
    SICILIAN_D6_E5 = "sicilian_d6_e5"
    SCHEVENINGEN = "scheveningen"
    KAN_TAIMANOV = "kan_taimanov"
    MAROCZY = "maroczy"
    FRENCH_CHAIN = "french_chain"
    KID_CLOSED = "kid_closed"
    BENONI = "benoni"
    CARLSBAD = "carlsbad"
    ISOLANI = "isolani"
    HANGING_PAWNS = "hanging_pawns"
    STONEWALL = "stonewall"
    LONDON = "london"
    SLAV = "slav"
    CARO = "caro"
    ITALIAN = "italian"
    SYMMETRIC_D = "symmetric_d"
    SCOTCH = "scotch"
    DOUBLED_C = "doubled_c"
    BIG_CENTER = "big_center"
    OPEN_CENTER = "open_center"


@dataclass(frozen=True, slots=True)
class Match:
    """Распознанная структура. `owner` — сторона, от лица которой записано правило
    (None — структура симметрична). `params` — клетки для текста (имена полей)."""

    id: StructureId
    owner: chess.Color | None
    params: dict[str, str] = field(default_factory=dict)


Rule = Callable[[chess.Board, PawnView, PawnView], dict[str, str] | None]


def _name(square: chess.Square) -> str:
    return chess.square_name(square)


def _hedgehog(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Ёж: b6, d6, e6 без c-пешки против c4 без d-пешки (у белых — зеркально)."""
    if not (own.has("b", 3) and own.has("d", 3) and own.has("e", 3) and own.none("c")):
        return None
    if not (other.has("c", 4) and other.none("d")):
        return None
    return {"b": _name(own.square("b", 3)), "d": _name(own.square("d", 3))}


def _sicilian_base(own: PawnView, other: PawnView) -> bool:
    """Сицилианский размен: своей c-пешки нет, у соперника e4 без d-пешки."""
    return own.none("c") and other.has("e", 4) and other.none("d")


def _sicilian_d6_e5(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Найдорф с …e5, Свешников, Болеславский: d6 + e5 против e4, дыра d5."""
    if not (_sicilian_base(own, other) and own.has("d", 3) and own.has("e", 4)):
        return None
    return {"pawn": _name(own.square("d", 3)), "hole": _name(own.square("d", 4))}


def _scheveningen(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Малый центр d6 + e6 против e4 (без «тисков» c4 — это уже Мароци)."""
    if not (_sicilian_base(own, other) and own.has("d", 3) and own.has("e", 3)):
        return None
    if other.has("c", 4):
        return None
    return {"d": _name(own.square("d", 3)), "e": _name(own.square("e", 3))}


def _kan_taimanov(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Тайманов / Кан: e6, d-пешка ещё на d7, против e4."""
    if not (_sicilian_base(own, other) and own.has("e", 3) and own.has("d", 2)):
        return None
    if other.has("c", 4):
        return None
    return {"pawn": _name(own.square("d", 2)), "hole": _name(own.square("d", 3))}


def _maroczy(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Тиски Мароци: c4 + e4 без d-пешки против соперника без c-пешки с d6/d7."""
    if not (own.has("c", 4) and own.has("e", 4) and own.none("d")):
        return None
    if not (other.none("c") and other.has("d", 2, 3)):
        return None
    return {"c": _name(own.square("c", 4)), "e": _name(own.square("e", 4))}


def _french_chain(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Французская цепь: d4 + e5 против d5 + e6."""
    if not (own.has("d", 4) and own.has("e", 5) and other.has("d", 4) and other.has("e", 3)):
        return None
    return {"d": _name(own.square("d", 4)), "e": _name(own.square("e", 5))}


def _kid_closed(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Закрытый центр староиндийского типа: d5 + e4 против d6 + e5."""
    if not (own.has("d", 5) and own.has("e", 4) and other.has("d", 3) and other.has("e", 4)):
        return None
    return {"d": _name(own.square("d", 5)), "e": _name(own.square("e", 4))}


def _benoni(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Современная Бенони: d5 и e-пешка без c-пешки против c5 + d6 без e-пешки."""
    if not (own.has("d", 5) and own.none("c") and own.has("e")):
        return None
    if not (other.has("c", 4) and other.has("d", 3) and other.none("e")):
        return None
    e_pawn = own.square("e", own.ranks("e")[-1])
    return {"pawn": _name(e_pawn), "target": _name(other.square("d", 3))}


def _carlsbad(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Карлсбад, владелец — сторона с атакой меньшинства: d4 + e-пешка без c-пешки
    против d5 + c-пешки без e-пешки (ферзевый гамбит с разменом; у Каро-Канн с
    разменом — зеркально по цвету)."""
    if not (own.has("d", 4) and own.has("e", 2, 3) and own.none("c") and own.has("b")):
        return None
    if not (other.has("d", 4) and other.has("c", 2, 3) and other.none("e")):
        return None
    b_pawn = own.square("b", own.ranks("b")[0])
    return {
        "pawn": _name(b_pawn),
        "target": _name(other.square("c", other.ranks("c")[-1])),
        "e": _name(own.square("e", own.ranks("e")[-1])),
        "square": _name(other.square("e", 5)),
        "support": _name(other.square("d", 4)),
    }


def _isolani(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Изолированная пешка d4 (у чёрных — d5), у соперника d-пешки нет."""
    if not (own.has("d", 4) and own.none("c") and own.none("e") and other.none("d")):
        return None
    return {"pawn": _name(own.square("d", 4)), "square": _name(own.square("d", 5))}


def _hanging(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Висячие пешки c4 + d4 без b- и e-пешек, у соперника нет c- и d-пешек."""
    if not (own.ranks("c") == [4] and own.ranks("d") == [4] and own.none("b") and own.none("e")):
        return None
    if not (other.none("c") and other.none("d")):
        return None
    return {"pawns": f"{_name(own.square('c', 4))},{_name(own.square('d', 4))}"}


def _stonewall(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """«Стоунволл»: d4, e3, f4 (у чёрных — d5, e6, f5)."""
    if not (own.has("d", 4) and own.has("e", 3) and own.has("f", 4)):
        return None
    return {
        "square": _name(own.square("e", 5)),
        "support": f"{_name(own.square('d', 4))},{_name(own.square('f', 4))}",
        "hole": _name(own.square("e", 4)),
    }


_LONDON_BISHOP = (chess.F4, chess.G3, chess.H2)


def _london(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Лондон (только белые): d4, e3, c2/c3, f2 на месте и чернопольный слон вне цепи."""
    if own.color != chess.WHITE:
        return None
    if not (own.has("d", 4) and own.has("e", 3) and own.has("c", 2, 3) and own.has("f", 2)):
        return None
    bishop = next(
        (s for s in _LONDON_BISHOP if board.piece_at(s) == chess.Piece(chess.BISHOP, chess.WHITE)),
        None,
    )
    if bishop is None:
        return None
    return {"bishop": _name(bishop), "pawn": "d4", "square": "e5"}


def _slav(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Славянская / Каро-Канн (только чёрные): c6 + d5 и e-пешка дома или на e6 против
    d4 и пешки c4 или e4, которая бьёт по d5."""
    if own.color != chess.BLACK:
        return None
    if not (own.has("c", 3) and own.has("d", 4) and own.has("e", 2, 3)):
        return None
    if not (other.has("d", 4) and (other.has("c", 4) or other.has("e", 4))):
        return None
    return {"support": "c6", "pawn": "d5"}


def _caro(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Главная Каро-Канн: c6 + e-пешка без d-пешки против d4 без e-пешки."""
    if not (own.has("c", 3) and own.has("e", 2, 3) and own.none("d")):
        return None
    if not (other.has("d", 4) and other.none("e") and other.has("c", 2, 3)):
        return None
    return {
        "target": _name(other.square("d", 4)),
        "square": _name(other.square("e", 5)),
    }


def _italian(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Медленная итальянская: c3 + d3 + e4 против e5 и d6/d7."""
    if not (own.has("c", 3) and own.has("d", 3) and own.has("e", 4)):
        return None
    if not (other.has("e", 4) and other.has("d", 2, 3)):
        return None
    d_pawn = other.square("d", other.ranks("d")[-1])
    return {
        "pawn": _name(own.square("d", 3)),
        "support": _name(own.square("c", 3)),
        "d": _name(d_pawn),
        "e": _name(other.square("e", 4)),
    }


def _scotch(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Шотландская / Филидор с разменом на d4: e4 без d-пешки против d6/d7 без e-пешки,
    c-пешки у обоих на месте (c4 у владельца — уже староиндийская со взятием на d4)."""
    if not (own.has("e", 4) and own.none("d") and own.has("c", 2, 3)):
        return None
    if not (other.has("d", 2, 3) and other.none("e") and other.has("c")):
        return None
    return {
        "pawn": _name(own.square("e", 4)),
        "d": _name(other.square("d", other.ranks("d")[-1])),
    }


def _doubled_c(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Сдвоенные c-пешки, передняя — на своей 4-й (Россолимо после Bxc6, Нимцович)."""
    ranks = own.ranks("c")
    if len(ranks) < 2 or ranks[-1] != 4:
        return None
    return {"pawns": ",".join(_name(own.square("c", r)) for r in sorted(ranks, reverse=True))}


def _big_center(board: chess.Board, own: PawnView, other: PawnView) -> dict[str, str] | None:
    """Пешечный центр d4 + e4, центральные пешки соперника не дальше своей 3-й."""
    if not (own.has("d", 4) and own.has("e", 4)):
        return None
    if any(r > 3 for f in ("d", "e") for r in other.ranks(f)):
        return None
    return {"pawns": f"{_name(own.square('d', 4))},{_name(own.square('e', 4))}"}


_RULES: tuple[tuple[StructureId, Rule], ...] = (
    (StructureId.HEDGEHOG, _hedgehog),
    (StructureId.SICILIAN_D6_E5, _sicilian_d6_e5),
    (StructureId.SCHEVENINGEN, _scheveningen),
    (StructureId.KAN_TAIMANOV, _kan_taimanov),
    (StructureId.MAROCZY, _maroczy),
    (StructureId.FRENCH_CHAIN, _french_chain),
    (StructureId.KID_CLOSED, _kid_closed),
    (StructureId.BENONI, _benoni),
    (StructureId.CARLSBAD, _carlsbad),
    (StructureId.ISOLANI, _isolani),
    (StructureId.HANGING_PAWNS, _hanging),
    (StructureId.STONEWALL, _stonewall),
    (StructureId.LONDON, _london),
    (StructureId.SLAV, _slav),
    (StructureId.CARO, _caro),
    (StructureId.ITALIAN, _italian),
)

_LATE_RULES: tuple[tuple[StructureId, Rule], ...] = (
    (StructureId.SCOTCH, _scotch),
    (StructureId.DOUBLED_C, _doubled_c),
    (StructureId.BIG_CENTER, _big_center),
)


def _symmetric_d(white: PawnView, black: PawnView) -> bool:
    """e4 против e5 без d-пешек: открытая линия d (Филидор с разменом на e5)."""
    return white.has("e", 4) and black.has("e", 4) and white.none("d") and black.none("d")


def _open_center(white: PawnView, black: PawnView) -> bool:
    """На линиях d и e осталось не больше одной пешки."""
    return sum(len(v.ranks(f)) for v in (white, black) for f in ("d", "e")) <= 1


CATALOG: tuple[StructureId, ...] = (
    *(sid for sid, _ in _RULES),
    StructureId.SYMMETRIC_D,
    *(sid for sid, _ in _LATE_RULES),
    StructureId.OPEN_CENTER,
)

# Структуры без владельца: правило про обе стороны сразу.
SYMMETRIC = frozenset({StructureId.SYMMETRIC_D, StructureId.OPEN_CENTER})


def recognize(board: chess.Board) -> list[Match]:
    """Все распознанные структуры в порядке `CATALOG`; в пределах одной — белые первыми."""
    views = {color: PawnView(board, color) for color in chess.COLORS}
    white, black = views[chess.WHITE], views[chess.BLACK]

    def owned(rules: tuple[tuple[StructureId, Rule], ...]) -> list[Match]:
        found = []
        for sid, rule in rules:
            for color in (chess.WHITE, chess.BLACK):
                params = rule(board, views[color], views[not color])
                if params is not None:
                    found.append(Match(sid, color, params))
        return found

    matches = owned(_RULES)
    if _symmetric_d(white, black):
        matches.append(Match(StructureId.SYMMETRIC_D, None))
    matches.extend(owned(_LATE_RULES))
    # Открытый центр — только если ничего точнее нет (изолятор без e-пешек тоже «открыт»).
    if not matches and _open_center(white, black):
        matches.append(Match(StructureId.OPEN_CENTER, None))
    return matches
