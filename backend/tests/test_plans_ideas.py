"""Идеи позиции (`app/plans/ideas.py`) и их тексты RU / EN (`app/plans/templates.py`).

Главное правило текста — только проверенные факты: клетки в тексте берутся из
параметров идеи (или записаны в самом шаблоне), ход в SAN легален для стороны идеи,
пешка в параметрах действительно стоит на доске.
"""

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

# Параметры, где записаны клетки пешек (любого цвета).
PAWN_PARAMS = {"pawn", "pawns", "target", "support", "base", "chain", "opp_chain", "d", "e"}
# Параметры-ходы в координатах «c7–c5»: с первой клетки ходит пешка стороны идеи.
MOVE_PARAMS = {"move", "b_break", "d_break"}


def boards() -> Iterator[tuple[str, chess.Board]]:
    for name in sorted(LINES):
        yield name, board_of(name)
    yield "open_files", chess.Board(OPEN_FILES_FEN)


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
