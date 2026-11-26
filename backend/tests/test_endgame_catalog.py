"""Каталог эндшпилей и разбор ответа таблиц: легальность, цели по зафиксированным ответам
Syzygy, точка зрения ходящего, порядок ходов (самая упорная защита), цель позиции из партии."""

from collections import Counter

import chess
import pytest

from app.endgames.__main__ import trim
from app.endgames.catalog import CATALOG, CatalogPosition, Category, catalog_position
from app.endgames.rules import goal_for
from app.endgames.tablebase import (
    TB_MAX_PIECES,
    TbMove,
    flip,
    normalize,
    parse_position,
    piece_count,
    query_fen,
    rank_moves,
)
from tests.endgame_fakes import fixture_answers

ANSWERS = fixture_answers()


def test_catalog_size_and_ids() -> None:
    assert len(CATALOG) >= 20
    ids = [p.id for p in CATALOG]
    assert len(set(ids)) == len(ids)
    assert all(len(i) <= 64 for i in ids)  # endgame_attempts.key
    assert catalog_position("rook_lucena") is not None
    assert catalog_position("nope") is None


def test_categories_covered() -> None:
    counts = Counter(p.category for p in CATALOG)
    assert set(counts) == set(Category)
    assert counts[Category.PAWN] >= 3
    assert counts[Category.ROOK] >= 3
    assert {p.difficulty for p in CATALOG} <= {1, 2, 3}


def test_required_themes_present() -> None:
    ids = {p.id for p in CATALOG}
    for theme in (
        "pawn_opposition_win",
        "pawn_square",
        "pawn_outside_passer",
        "rook_lucena",
        "rook_philidor",
        "rook_vs_pawn_win",
        "queen_vs_pawn",
        "mate_queen",
        "mate_rook",
        "mate_two_bishops",
        "mate_bishop_knight",
    ):
        assert theme in ids


@pytest.mark.parametrize("position", CATALOG, ids=lambda p: p.id)
def test_position_is_legal_and_in_tablebase(position: CatalogPosition) -> None:
    board = chess.Board(position.fen)
    assert board.is_valid(), board.status()
    assert not board.is_game_over()
    assert piece_count(board) <= TB_MAX_PIECES
    # Каталог не зависит от счётчиков: кэш и ответы таблиц — по расстановке.
    assert query_fen(board) == position.fen


@pytest.mark.parametrize("position", CATALOG, ids=lambda p: p.id)
def test_goal_matches_syzygy(position: CatalogPosition) -> None:
    """Цель = ответ таблиц для ходящего (зафиксирован с tablebase.lichess.ovh)."""
    answer = parse_position(ANSWERS[position.fen])
    assert answer.category == position.goal
    # Цель достижима ходом ученика: лучший ход сохраняет результат, и есть ходы хуже
    # (кроме чисто технических матов) — иначе тренировать нечего.
    assert answer.moves[0].category == position.goal
    if position.category is not Category.MATE and position.id != "pawn_outside_passer_2":
        assert any(m.category != position.goal for m in answer.moves)


def test_fixture_is_exactly_catalog() -> None:
    assert set(ANSWERS) == {p.fen for p in CATALOG}
    # Фикстура уже сокращена до разбираемых полей.
    for raw in ANSWERS.values():
        assert trim(raw) == raw


def test_unique_saving_moves() -> None:
    """Учебные «единственные ходы» — как в подсказках каталога."""

    def saving(position_id: str) -> list[str]:
        position = catalog_position(position_id)
        assert position is not None
        answer = parse_position(ANSWERS[position.fen])
        return [m.san for m in answer.moves if m.category == position.goal]

    assert saving("pawn_opposition_draw") == ["Ke5"]
    assert saving("rook_philidor_checks") == ["Re1+"]
    assert "Ra6" in saving("rook_philidor")
    assert set(saving("pawn_square")) == {"Ke4", "Ke5"}
    assert "Kb3" in saving("queen_vs_rook_pawn")
    assert all(san.startswith("Rf") for san in saving("rook_vancura"))


def test_perspective_is_flipped_for_moves() -> None:
    """У Lichess категория хода — глазами соперника; наружу — глазами ходящего."""
    raw = ANSWERS["1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1"]
    lichess_first = next(m for m in raw["moves"] if m["san"] == "Rd1+")
    assert lichess_first["category"] == "loss"
    parsed = parse_position(raw)
    assert parsed.category == "win"
    rd1 = next(m for m in parsed.moves if m.san == "Rd1+")
    assert rd1.category == "win"
    assert rd1.dtz == -lichess_first["dtz"]
    assert rd1.dtz is not None
    assert rd1.dtz > 0


def test_mate_first_then_shortest_win() -> None:
    raw = {
        "category": "win",
        "dtz": 3,
        "dtm": 3,
        "checkmate": False,
        "stalemate": False,
        "moves": [
            {"uci": "a1a2", "san": "Ra2", "category": "draw", "dtz": 0, "dtm": 0},
            {"uci": "b1b2", "san": "Qb2", "category": "loss", "dtz": -5, "dtm": -5},
            {"uci": "c1c2", "san": "Qc2", "category": "loss", "dtz": -2, "dtm": -2},
            {
                "uci": "d1d8",
                "san": "Qd8#",
                "category": "loss",
                "dtz": 0,
                "dtm": 0,
                "checkmate": True,
            },
            {"uci": "e1e2", "san": "Ke2", "category": "win", "dtz": 7, "dtm": 9},
        ],
    }
    parsed = parse_position(raw)
    assert [m.san for m in parsed.moves] == ["Qd8#", "Qc2", "Qb2", "Ra2", "Ke2"]
    assert parsed.moves[0].checkmate


def test_stubborn_defense_first_when_losing() -> None:
    """Проигрывающей стороне лучший ход — тот, что держится дольше всего."""
    moves = [
        TbMove("a", "a", "loss", dtz=-3, dtm=-10),
        TbMove("b", "b", "loss", dtz=-9, dtm=-30),
        TbMove("c", "c", "blessed-loss", dtz=-120, dtm=None),
        TbMove("d", "d", "loss", dtz=-15, dtm=None),
    ]
    assert [m.uci for m in rank_moves(moves)] == ["c", "b", "d", "a"]


def test_rank_is_stable_for_draws() -> None:
    moves = [TbMove(x, x, "draw", 0, 0) for x in "xyz"] + [TbMove("w", "w", "win", 4, 9)]
    assert [m.uci for m in rank_moves(moves)] == ["w", "x", "y", "z"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("win", "win"),
        ("maybe-win", "win"),
        ("syzygy-win", "win"),
        ("cursed-win", "cursed-win"),
        ("draw", "draw"),
        ("blessed-loss", "blessed-loss"),
        ("maybe-loss", "loss"),
        ("syzygy-loss", "loss"),
        ("loss", "loss"),
        ("unknown", "unknown"),
        (None, "unknown"),
        ("что-то", "unknown"),
    ],
)
def test_normalize(raw: object, expected: str) -> None:
    assert normalize(raw) == expected


def test_flip_is_involution() -> None:
    for category in ("win", "cursed-win", "draw", "blessed-loss", "loss", "unknown"):
        assert flip(flip(category)) == category
    assert flip("cursed-win") == "blessed-loss"


def test_query_fen_drops_clocks() -> None:
    board = chess.Board("8/8/8/4k3/8/8/8/R3K3 w - - 37 80")
    assert query_fen(board) == "8/8/8/4k3/8/8/8/R3K3 w - - 0 1"


@pytest.mark.parametrize(
    ("win", "goal"),
    [(99.0, "win"), (65.0, "win"), (64.9, "draw"), (50.0, "draw"), (35.0, "draw"), (34.9, None)],
)
def test_goal_for(win: float, goal: str | None) -> None:
    assert goal_for(win) == goal
