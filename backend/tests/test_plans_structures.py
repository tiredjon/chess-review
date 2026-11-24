"""Каталог пешечных структур (`app/plans/structures.py`) на позициях из реальных дебютов.

`EXPECTED` — точный результат распознавания для каждой линии из `plans_lines.LINES`:
положительные примеры структуры и «почти она» (соседние дебюты, где правило не должно
сработать). Мета-тест следит, чтобы у каждой структуры было ≥3 положительных и ≥2
отрицательных позиций; зеркальный тест — что правило ловит структуру за любой цвет.
"""

import chess
import pytest

from app.plans.structures import CATALOG, SYMMETRIC, Match, StructureId, recognize
from tests.plans_lines import LINES, board_of

S = StructureId
W, B = chess.WHITE, chess.BLACK

# Структура и её владелец (None — симметричная) в порядке `CATALOG`.
EXPECTED: dict[str, tuple[tuple[StructureId, chess.Color | None], ...]] = {
    "hedgehog_english": ((S.HEDGEHOG, B), (S.MAROCZY, W)),
    "hedgehog_kan": ((S.HEDGEHOG, B), (S.MAROCZY, W)),
    "hedgehog_rd1": ((S.HEDGEHOG, B),),
    "accel_dragon_maroczy": ((S.MAROCZY, W),),
    "taimanov_maroczy": ((S.MAROCZY, W),),
    "maroczy_nd4": ((S.MAROCZY, W),),
    "najdorf_be2_e5": ((S.SICILIAN_D6_E5, B),),
    "sveshnikov": ((S.SICILIAN_D6_E5, B),),
    "boleslavsky": ((S.SICILIAN_D6_E5, B),),
    "kalashnikov": ((S.SICILIAN_D6_E5, B),),
    "scheveningen": ((S.SCHEVENINGEN, B),),
    "keres_attack": ((S.SCHEVENINGEN, B),),
    "najdorf_english": ((S.SCHEVENINGEN, B),),
    "taimanov_english": ((S.KAN_TAIMANOV, B),),
    "taimanov_be2": ((S.KAN_TAIMANOV, B),),
    "kan_bd3": ((S.KAN_TAIMANOV, B),),
    "dragon_yugoslav": (),
    "rossolimo_dxc6": ((S.DOUBLED_C, B),),
    "rossolimo_bxc6": ((S.DOUBLED_C, B),),
    "nimzo_saemisch": ((S.DOUBLED_C, W),),
    "rossolimo_g6": (),
    "french_advance": ((S.FRENCH_CHAIN, W),),
    "french_steinitz": ((S.FRENCH_CHAIN, W),),
    "french_tarrasch_closed": ((S.FRENCH_CHAIN, W),),
    "caro_advance": ((S.FRENCH_CHAIN, W),),
    "french_exchange": (),
    "french_rubinstein": (),
    "french_2d4d5": (),
    "kid_mar_del_plata": ((S.KID_CLOSED, W),),
    "kid_petrosian": ((S.KID_CLOSED, W),),
    "czech_benoni": ((S.KID_CLOSED, W),),
    "ruy_chigorin_d5": ((S.KID_CLOSED, W),),
    "kid_exd4": (),
    "benoni_classical": ((S.BENONI, W),),
    "benoni_fianchetto": ((S.BENONI, W),),
    "benoni_taimanov": ((S.BENONI, W),),
    "qgd_exchange": ((S.CARLSBAD, W),),
    "caro_exchange": ((S.CARLSBAD, B),),
    "qgd_exchange_bf4": ((S.CARLSBAD, W),),
    "slav_exchange": (),
    "qgd_orthodox": (),
    "panov": ((S.ISOLANI, W),),
    "qga_iqp": ((S.ISOLANI, W),),
    "alapin_iqp": ((S.ISOLANI, W),),
    "tarrasch_iqp": ((S.ISOLANI, B),),
    "french_tarrasch_iqp": ((S.ISOLANI, B),),
    "tartakower_hanging": ((S.HANGING_PAWNS, B),),
    "semi_tarrasch_hanging": ((S.HANGING_PAWNS, W),),
    "panov_hanging": ((S.HANGING_PAWNS, W),),
    "dutch_stonewall": ((S.STONEWALL, B), (S.SLAV, B)),
    "stonewall_attack": ((S.STONEWALL, W),),
    "dutch_stonewall_b3": ((S.STONEWALL, B), (S.SLAV, B)),
    "dutch_leningrad": (),
    "london_c5": ((S.LONDON, W),),
    "london_kid": ((S.LONDON, W),),
    "london_qb6": ((S.LONDON, W),),
    "london_c6": ((S.LONDON, W),),
    "colle": (),
    "semi_slav": ((S.SLAV, B),),
    "slav_bf5": ((S.SLAV, B),),
    "caro_nc3": ((S.SLAV, B),),
    "slav_dxc4": (),
    "caro_classical": ((S.CARO, B),),
    "caro_karpov": ((S.CARO, B),),
    "caro_bronstein": ((S.CARO, B),),
    "giuoco_pianissimo": ((S.ITALIAN, W),),
    "two_knights_d3": ((S.ITALIAN, W),),
    "ruy_d3": ((S.ITALIAN, W),),
    "italian_early": (),
    "greco": ((S.BIG_CENTER, W),),
    "philidor_hanham_dxe5": ((S.SYMMETRIC_D, None),),
    "philidor_queenless": ((S.SYMMETRIC_D, None),),
    "philidor_lion_dxe5": ((S.SYMMETRIC_D, None),),
    "philidor_exchange": ((S.SCOTCH, W),),
    "scotch_four_knights": ((S.SCOTCH, W),),
    "scotch_bc5": ((S.SCOTCH, W),),
    "scotch_mieses": (),
    "owen": ((S.BIG_CENTER, W),),
    "pirc_austrian": ((S.BIG_CENTER, W),),
    "grunfeld_exchange": ((S.BIG_CENTER, W),),
    "two_knights_open": ((S.OPEN_CENTER, None),),
    "max_lange": ((S.OPEN_CENTER, None),),
    "danish": ((S.OPEN_CENTER, None),),
    "start": (),
}

# Соседние дебюты, где структура почти есть, но правило срабатывать не должно.
NEAR_MISS: dict[StructureId, tuple[str, ...]] = {
    S.HEDGEHOG: ("accel_dragon_maroczy", "scheveningen"),
    S.SICILIAN_D6_E5: ("scheveningen", "najdorf_english", "dragon_yugoslav"),
    S.SCHEVENINGEN: ("najdorf_be2_e5", "taimanov_maroczy", "taimanov_english"),
    S.KAN_TAIMANOV: ("scheveningen", "keres_attack", "taimanov_maroczy"),
    S.MAROCZY: ("hedgehog_rd1", "scheveningen"),
    S.FRENCH_CHAIN: ("french_exchange", "french_rubinstein", "french_2d4d5"),
    S.KID_CLOSED: ("benoni_classical", "kid_exd4"),
    S.BENONI: ("czech_benoni", "kid_mar_del_plata"),
    S.CARLSBAD: ("slav_exchange", "qgd_orthodox", "panov"),
    S.ISOLANI: ("caro_exchange", "tartakower_hanging"),
    S.HANGING_PAWNS: ("panov", "qgd_orthodox"),
    S.STONEWALL: ("dutch_leningrad", "colle", "london_c5"),
    S.LONDON: ("colle", "stonewall_attack"),
    S.SLAV: ("slav_exchange", "london_c6", "caro_classical"),
    S.CARO: ("caro_advance", "caro_exchange", "french_rubinstein"),
    S.ITALIAN: ("greco", "italian_early"),
    S.SYMMETRIC_D: ("philidor_exchange", "scotch_four_knights"),
    S.SCOTCH: ("scotch_mieses", "kid_exd4", "philidor_hanham_dxe5"),
    S.DOUBLED_C: ("rossolimo_g6", "scotch_mieses"),
    S.BIG_CENTER: ("french_advance", "italian_early", "french_2d4d5"),
    S.OPEN_CENTER: ("french_exchange", "scotch_four_knights", "french_tarrasch_iqp"),
}

# Структуры, привязанные к цвету: зеркально не ищутся.
COLOR_BOUND = {S.LONDON: W, S.SLAV: B}

PAWN_PARAMS = {"pawn", "pawns", "target", "support", "b", "c", "d", "e"}


def found(board: chess.Board) -> tuple[tuple[StructureId, chess.Color | None], ...]:
    return tuple((m.id, m.owner) for m in recognize(board))


def test_lines_and_expectations_agree() -> None:
    assert set(EXPECTED) == set(LINES)


@pytest.mark.parametrize("line", sorted(EXPECTED))
def test_recognize(line: str) -> None:
    assert found(board_of(line)) == EXPECTED[line]


@pytest.mark.parametrize("sid", list(StructureId))
def test_catalog_has_examples(sid: StructureId) -> None:
    positives = [line for line, items in EXPECTED.items() if any(s == sid for s, _ in items)]
    assert len(positives) >= 3, positives
    misses = NEAR_MISS[sid]
    assert len(misses) >= 2
    for line in misses:
        assert sid not in {s for s, _ in found(board_of(line))}, line


def test_catalog_order() -> None:
    assert set(CATALOG) == set(StructureId)
    assert len(CATALOG) == len(StructureId)
    for items in EXPECTED.values():
        ranks = [CATALOG.index(s) for s, _ in items]
        assert ranks == sorted(ranks)
    for line, items in EXPECTED.items():
        for sid, owner in items:
            assert (owner is None) == (sid in SYMMETRIC), line


def _agnostic(board: chess.Board, flip: bool) -> set[tuple[StructureId, chess.Color | None]]:
    return {
        (sid, None if owner is None else (not owner if flip else owner))
        for sid, owner in found(board)
        if sid not in COLOR_BOUND
    }


@pytest.mark.parametrize("line", sorted(EXPECTED))
def test_mirror_swaps_owner(line: str) -> None:
    """Зеркальная позиция — та же структура за другой цвет (кроме Лондона и славянской)."""
    board = board_of(line)
    assert _agnostic(board.mirror(), flip=True) == _agnostic(board, flip=False)


@pytest.mark.parametrize("line", ["london_c5", "london_kid", "london_qb6", "london_c6"])
def test_london_is_white_only(line: str) -> None:
    assert S.LONDON not in {s for s, _ in found(board_of(line).mirror())}


@pytest.mark.parametrize("line", ["semi_slav", "caro_nc3"])
def test_slav_is_black_only(line: str) -> None:
    assert S.SLAV not in {s for s, _ in found(board_of(line).mirror())}


@pytest.mark.parametrize(
    ("line", "params"),
    [
        (
            "qgd_exchange",
            {"pawn": "b2", "target": "c6", "e": "e3", "square": "e4", "support": "d5"},
        ),
        (
            "caro_exchange",
            {"pawn": "b7", "target": "c3", "e": "e7", "square": "e5", "support": "d4"},
        ),
        ("panov", {"pawn": "d4", "square": "d5"}),
        ("tarrasch_iqp", {"pawn": "d5", "square": "d4"}),
        ("tartakower_hanging", {"pawns": "c5,d5"}),
        ("najdorf_be2_e5", {"pawn": "d6", "hole": "d5"}),
        ("taimanov_be2", {"pawn": "d7", "hole": "d6"}),
        ("french_advance", {"d": "d4", "e": "e5"}),
        ("rossolimo_dxc6", {"pawns": "c5,c6"}),
        ("london_c5", {"bishop": "g3", "pawn": "d4", "square": "e5"}),
        ("giuoco_pianissimo", {"pawn": "d3", "support": "c3", "d": "d6", "e": "e5"}),
        ("philidor_exchange", {"pawn": "e4", "d": "d6"}),
        ("hedgehog_rd1", {"b": "b6", "d": "d6"}),
    ],
)
def test_first_match_params(line: str, params: dict[str, str]) -> None:
    assert recognize(board_of(line))[0].params == params


def _check_params(board: chess.Board, match: Match) -> None:
    for name, value in match.params.items():
        for square_name in value.split(","):
            square = chess.parse_square(square_name)
            piece = board.piece_at(square)
            if name in PAWN_PARAMS:
                assert piece is not None, (match.id, name, square_name)
                assert piece.piece_type == chess.PAWN, (match.id, name, square_name)
            elif name == "bishop":
                assert piece == chess.Piece(chess.BISHOP, match.owner is not False)


@pytest.mark.parametrize("line", sorted(EXPECTED))
def test_params_are_facts(line: str) -> None:
    """Каждое поле в параметрах — настоящая клетка; пешечные параметры стоят на пешках."""
    board = board_of(line)
    for match in recognize(board):
        _check_params(board, match)
