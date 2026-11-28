"""Идеи позиции (`app/plans/ideas.py`) и их тексты RU / EN (`app/plans/templates.py`).

Главное правило текста — только проверенные факты: клетки в тексте берутся из
параметров идеи (или записаны в самом шаблоне), ход в SAN легален для стороны идеи,
пешка в параметрах действительно стоит на доске.
"""

import itertools
import re
from collections.abc import Iterator

import chess
import pytest

from app.explain.templates import Lang
from app.plans.breaks import as_mover
from app.plans.ideas import MAX_IDEAS_PER_SIDE, MAX_STRUCTURES, position_ideas
from app.plans.structures import StructureId
from app.plans.templates import IDEAS, STRUCTURES, render, render_idea
from app.plans.types import Idea, PositionIdeas
from tests.plans_lines import LINES, board_of

LANGS: tuple[Lang, ...] = ("ru", "en")
SQUARE = re.compile(r"[a-h][1-8]")
PLACEHOLDER = re.compile(r"\{\w+\}")
# Синтетика: открыты линии c и f — ключ `rook_open_files` в дебютных линиях не встречается.
OPEN_FILES_FEN = "r3k2r/pp2p1pp/3p4/8/8/3P4/PP2P1PP/R3K2R w KQkq - 0 1"
# Синтетика миттельшпиля: укрытие короля, 7-я горизонталь, конь на краю.
MIDDLEGAME_FENS: dict[str, str] = {
    # Ласкер, диаграмма 95: …g6 при слоне g7 — разменяйте его.
    "fianchetto_defender": "r2q1rk1/pbppnpbp/1pn1p1p1/4P3/3P4/2NBBN2/PPP2PPP/R2Q1RK1 w - - 0 1",
    # Та же позиция без чёрнопольного слона у чёрных: f6 и h6 — дыры.
    "king_holes": "r2q1rk1/pbppnp1p/1pn1p1p1/4P3/3P4/2NB1N2/PPP2PPP/R2Q1RK1 w - - 0 1",
    # Разносторонние рокировки, у чёрных …h6: зацепка для g2–g4.
    "pawn_hook": "r1bq1rk1/pp2bpp1/2n1pn1p/3p4/3P4/2N1PN2/PPQ1BPPP/2KR3R w - - 0 1",
    # Лазар — Ласкер (Париж, 1914), диаграмма 99: ладья по открытой линии b на b2.
    "rook_to_seventh": "1r3rk1/p1p2ppp/2p5/8/8/5B2/P1P2PPP/R4RK1 b - - 0 1",
    "rook_seventh": "6k1/pR3ppp/8/8/8/8/5PPP/6K1 w - - 0 1",
    "knight_rim": "r1bqkb1r/pppp1ppp/5n2/4p3/n3P3/2N2N2/PPPP1PPP/R1BQKB1R b KQkq - 0 1",
}

# Параметры, где записаны клетки пешек (любого цвета).
PAWN_PARAMS = {"pawn", "pawns", "target", "support", "base", "chain", "opp_chain", "d", "e"}
# Параметры-ходы в координатах «c7–c5»: с первой клетки ходит пешка стороны идеи.
MOVE_PARAMS = {"move", "b_break", "d_break"}


def boards() -> Iterator[tuple[str, chess.Board]]:
    for name in sorted(LINES):
        yield name, board_of(name)
    yield "open_files", chess.Board(OPEN_FILES_FEN)
    for name, fen in MIDDLEGAME_FENS.items():
        yield name, chess.Board(fen)


ALL = list(boards())
IDS = [name for name, _ in ALL]


def color_of(side: str) -> chess.Color:
    return chess.WHITE if side == "white" else chess.BLACK


def test_every_idea_key_is_reached() -> None:
    reached = {idea.key for _, board in ALL for idea in position_ideas(board).ideas}
    assert reached == set(IDEAS)


def test_every_structure_has_texts() -> None:
    assert set(STRUCTURES) == {sid.value for sid in StructureId}
    for sid, structure in STRUCTURES.items():
        for lang in LANGS:
            assert structure.title[lang].strip(), (sid, lang)
            assert structure.summary[lang].strip(), (sid, lang)
    for key, template in IDEAS.items():
        assert set(template) == set(LANGS), key
        assert all(template[lang].strip() for lang in LANGS), key


def test_structure_plans_have_templates() -> None:
    """Каждая структура даёт хотя бы один свой пункт плана в каком-то дебюте."""
    plans = {key.split(".")[0] for key in IDEAS if "." in key}
    assert plans == {sid.value for sid in StructureId}


@pytest.mark.parametrize(("name", "board"), ALL, ids=IDS)
@pytest.mark.parametrize("lang", LANGS)
def test_render_is_complete(name: str, board: chess.Board, lang: Lang) -> None:
    ideas = position_ideas(board)
    rendered = render(ideas, lang)
    assert rendered.structures == ideas.structures
    assert [(r.key, r.side) for r in rendered.ideas] == [(i.key, i.side) for i in ideas.ideas]
    texts = [r.text for r in rendered.ideas]
    if ideas.structures:
        assert rendered.structure_title
        assert rendered.structure_summary
        texts += [rendered.structure_title, rendered.structure_summary]
    else:
        assert rendered.structure_title is None
        assert rendered.structure_summary is None
    for text in texts:
        assert not PLACEHOLDER.search(text), text
        assert "{" not in text, text
        assert "}" not in text, text
        assert text == text.strip()


def _param_squares(idea: Idea) -> set[str]:
    return {sq for value in idea.params.values() for sq in SQUARE.findall(value)}


@pytest.mark.parametrize(("name", "board"), ALL, ids=IDS)
@pytest.mark.parametrize("lang", LANGS)
def test_squares_in_text_come_from_facts(name: str, board: chess.Board, lang: Lang) -> None:
    for idea in position_ideas(board).ideas:
        text = render_idea(idea, lang).text
        allowed = _param_squares(idea) | set(SQUARE.findall(IDEAS[idea.key][lang]))
        assert set(SQUARE.findall(text)) <= allowed, (idea, text)


MIDDLEGAME_PARAMS = {"knight", "route", "squares"}


def _check_middlegame_param(board: chess.Board, idea: Idea, name: str, value: str) -> None:
    """Конь — на месте, маршрут — ходы коня по свободным полям, дыры — не пешки."""
    color = color_of(idea.side)
    if name == "knight":
        assert board.piece_at(chess.parse_square(value)) == chess.Piece(chess.KNIGHT, color)
    elif name == "route":
        squares = [chess.parse_square(sq) for sq in value.split("–")]
        assert board.piece_at(squares[0]) == chess.Piece(chess.KNIGHT, color), idea
        for start, end in itertools.pairwise(squares):
            assert end in chess.SquareSet(chess.BB_KNIGHT_ATTACKS[start]), idea
        assert all(board.piece_at(sq) is None for sq in squares[1:]), idea
    else:
        for square in value.split(","):
            assert board.piece_type_at(chess.parse_square(square)) != chess.PAWN, idea


def _check_idea(board: chess.Board, idea: Idea) -> None:
    color = color_of(idea.side)
    for name, value in idea.params.items():
        if name in PAWN_PARAMS:
            for square in SQUARE.findall(value):
                piece = board.piece_at(chess.parse_square(square))
                assert piece is not None, (idea, square)
                assert piece.piece_type == chess.PAWN, (idea, square)
        elif name in MOVE_PARAMS:
            start, end = value.split("–")
            piece = board.piece_at(chess.parse_square(start))
            assert piece == chess.Piece(chess.PAWN, color), idea
            assert chess.square_file(chess.parse_square(start)) == chess.square_file(
                chess.parse_square(end)
            )
        elif name == "san":
            mover = as_mover(board, color)
            assert mover is not None, idea
            mover.parse_san(value)  # бросит исключение, если ход нелегален
        elif name in MIDDLEGAME_PARAMS:
            _check_middlegame_param(board, idea, name, value)
        elif name == "bishop":
            assert board.piece_type_at(chess.parse_square(value)) == chess.BISHOP, idea
        elif name == "pieces":
            for item in value.split(","):
                piece = board.piece_at(chess.parse_square(item[1:]))
                assert piece is not None, idea
                assert piece.symbol().upper() == item[0], idea
        elif name in {"file", "files"}:
            assert all(f in "abcdefgh" for f in value.split(",")), idea
        elif name == "wing":
            assert value in {"queenside", "kingside"}, idea


@pytest.mark.parametrize(("name", "board"), ALL, ids=IDS)
def test_idea_params_are_facts(name: str, board: chess.Board) -> None:
    for idea in position_ideas(board).ideas:
        _check_idea(board, idea)


@pytest.mark.parametrize(("name", "board"), ALL, ids=IDS)
def test_idea_limits_and_order(name: str, board: chess.Board) -> None:
    ideas = position_ideas(board)
    assert len(ideas.structures) <= MAX_STRUCTURES
    for side in ("white", "black"):
        assert sum(1 for i in ideas.ideas if i.side == side) <= MAX_IDEAS_PER_SIDE
    assert len({(i.side, i.key) for i in ideas.ideas}) == len(ideas.ideas)
    # Планы структуры идут раньше общих идей.
    planned = [any(i.key.startswith(f"{s}.") for s in ideas.structures) for i in ideas.ideas]
    assert planned == sorted(planned, reverse=True)


@pytest.mark.parametrize(("name", "board"), ALL, ids=IDS)
def test_facts_mirror_pawns(name: str, board: chess.Board) -> None:
    """Слабости и форпосты — реальные клетки; линии — буквы."""
    ideas = position_ideas(board)
    for weakness in ideas.weaknesses:
        square = chess.parse_square(weakness.square)
        if weakness.kind == "hole":
            assert board.piece_type_at(square) != chess.PAWN
        else:
            assert board.piece_at(square) == chess.Piece(chess.PAWN, color_of(weakness.side))
    for outpost in ideas.outposts:
        assert board.piece_type_at(chess.parse_square(outpost.square)) != chess.PAWN
    assert all(f in "abcdefgh" for f in ideas.open_files)
    assert PositionIdeas.model_validate_json(ideas.model_dump_json()) == ideas


def test_najdorf_ideas() -> None:
    ideas = position_ideas(board_of("najdorf_be2_e5"))
    assert ideas.structures == ("sicilian_d6_e5",)
    assert [(i.side, i.key) for i in ideas.ideas[:2]] == [
        ("black", "sicilian_d6_e5.d5_break"),
        ("white", "sicilian_d6_e5.d5"),
    ]
    assert ideas.ideas[1].params == {"square": "d5", "pieces": "Nf6"}
    assert ("black", "d6", "backward") in {(w.side, w.square, w.kind) for w in ideas.weaknesses}
    assert ("white", "d5") in {(o.side, o.square) for o in ideas.outposts}
    assert ideas.half_open_files == {"white": ("d",), "black": ("c",)}


def test_owner_colors_in_summary() -> None:
    """Владелец структуры в тексте — та сторона, у которой она есть."""
    black = render(position_ideas(board_of("tarrasch_iqp")), "ru")
    white = render(position_ideas(board_of("panov")), "ru")
    assert black.structure_title == "Изолированная пешка d5"
    assert black.structure_summary is not None
    assert black.structure_summary.startswith("У чёрных изолированная пешка d5")
    assert white.structure_summary is not None
    assert white.structure_summary.startswith("У белых изолированная пешка d4")
    english = render(position_ideas(board_of("tarrasch_iqp")), "en")
    assert english.structure_summary is not None
    assert "Black" in english.structure_summary


def test_black_moves_get_ellipsis() -> None:
    rendered = {
        (r.side, r.key): r.text
        for r in render(position_ideas(board_of("najdorf_be2_e5")), "ru").ideas
    }
    assert "…d5" in rendered[("black", "sicilian_d6_e5.d5_break")]
    assert "f4" in rendered[("white", "pawn_break_now")]
    assert "…f4" not in rendered[("white", "pawn_break_now")]


def test_render_values() -> None:
    idea = Idea(key="outpost", side="white", params={"square": "d5", "support": "c4,e4"})
    assert render_idea(idea, "ru").text.count("пешки c4 и e4") == 1
    assert "c4 and e4" in render_idea(idea, "en").text
    single = Idea(key="outpost", side="white", params={"square": "d5", "support": "e4"})
    assert "пешка e4" in render_idea(single, "ru").text
    pieces = Idea(
        key="sicilian_d6_e5.d5", side="white", params={"square": "d5", "pieces": "Nf6,Be6"}
    )
    assert "конь f6, слон e6" in render_idea(pieces, "ru").text
    assert "knight f6, bishop e6" in render_idea(pieces, "en").text
    wing = Idea(
        key="majority", side="black", params={"wing": "queenside", "own": "3", "other": "2"}
    )
    assert "ферзевом" in render_idea(wing, "ru").text
    assert "queenside" in render_idea(wing, "en").text


def test_render_without_owner_idea() -> None:
    """Идеи собраны не `position_ideas`: заголовок без подстановок, описания нет."""
    bare = PositionIdeas(structures=("isolani",))
    rendered = render(bare, "ru")
    assert rendered.structure_title == "Изолированная пешка"
    assert rendered.structure_summary is None
    assert rendered.ideas == ()
    symmetric = render(PositionIdeas(structures=("open_center",)), "en")
    assert symmetric.structure_title
    assert symmetric.structure_summary


def test_open_files_synthetic() -> None:
    ideas = position_ideas(chess.Board(OPEN_FILES_FEN))
    assert ideas.open_files == ("c", "f")
    keys = {(i.side, i.key) for i in ideas.ideas}
    assert keys == {("white", "rook_open_files"), ("black", "rook_open_files")}
    text = render(ideas, "ru").ideas[0].text
    assert "c и f" in text


def test_start_position_is_quiet() -> None:
    ideas = position_ideas(chess.Board())
    assert ideas.structures == ()
    assert ideas.breaks == ()
    assert ideas.weaknesses == ()
    assert ideas.open_files == ()


def _keys(fen_name: str) -> dict[tuple[str, str], dict[str, str]]:
    ideas = position_ideas(chess.Board(MIDDLEGAME_FENS[fen_name])).ideas
    return {(i.side, i.key): i.params for i in ideas}


def test_king_shelter() -> None:
    assert _keys("fianchetto_defender")[("white", "trade_king_bishop")] == {
        "bishop": "g7",
        "squares": "f6,h6",
    }
    holes = _keys("king_holes")
    assert holes[("white", "king_holes")] == {"pawn": "g6", "squares": "f6,h6"}
    assert ("white", "trade_king_bishop") not in holes
    assert _keys("pawn_hook")[("white", "pawn_hook")] == {"pawn": "h6", "move": "g2–g4"}
    text = render(position_ideas(chess.Board(MIDDLEGAME_FENS["king_holes"])), "ru").ideas[0].text
    assert "f6 и h6" in text


def test_pawn_hook_needs_safe_own_king() -> None:
    """Короли на одном фланге — штурм пешками ослабил бы своего короля: зацепки нет."""
    same_wing = "r1bq1rk1/pp2bpp1/2n1pn1p/3p4/3P4/2N1PN2/PPQ1BPPP/R4RK1 w - - 0 1"
    keys = {i.key for i in position_ideas(chess.Board(same_wing)).ideas}
    assert "pawn_hook" not in keys


def test_no_shelter_ideas_without_queen() -> None:
    queenless = "r4rk1/pbppnpbp/1pn1p1p1/4P3/3P4/2NBBN2/PPP2PPP/R4RK1 w - - 0 1"
    keys = {i.key for i in position_ideas(chess.Board(queenless)).ideas}
    assert not keys & {"king_holes", "trade_king_bishop", "pawn_hook"}


def test_rook_seventh() -> None:
    assert _keys("rook_to_seventh")[("black", "rook_to_seventh")] == {"san": "Rb2"}
    rendered = render(position_ideas(chess.Board(MIDDLEGAME_FENS["rook_to_seventh"])), "ru")
    assert any("…Rb2" in r.text for r in rendered.ideas)
    on7 = _keys("rook_seventh")
    assert on7[("white", "rook_seventh")] == {"square": "b7"}
    assert ("white", "rook_to_seventh") not in on7


def test_rook_seventh_square_must_be_safe() -> None:
    """Поле вторжения под боем фигуры соперника — не предлагаем."""
    guarded = "1r3rk1/p1p2ppp/2p5/8/8/8/P1P2PPP/R1B2RK1 b - - 0 1"
    keys = {i.key for i in position_ideas(chess.Board(guarded)).ideas}
    assert "rook_to_seventh" not in keys


def test_knight_rim_route() -> None:
    assert _keys("knight_rim")[("black", "knight_rim")] == {"knight": "a4", "route": "a4–c5"}
    taimanov = {
        (i.side, i.key): i.params for i in position_ideas(board_of("taimanov_maroczy")).ideas
    }
    assert taimanov[("white", "knight_rim")]["route"].startswith("a3–")
