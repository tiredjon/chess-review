"""Факты для объяснений (SPEC §6.1) на настоящем разборе Оперной партии."""

from dataclasses import replace
from typing import Any

import pytest

from app.explain.facts import (
    facts_hash,
    format_eval,
    game_facts,
    grounded_tokens,
    is_explained,
    material_swing,
    motif_facts,
    move_facts,
)
from app.review.types import MoveClass
from tests.explain_data import opera_info, opera_move, opera_moves


@pytest.mark.parametrize(
    ("cp", "mate", "text"),
    [
        (80, None, "+0.80"),
        (-320, None, "-3.20"),
        (0, None, "+0.00"),
        (None, 3, "#3"),
        (None, -2, "-#2"),
        (None, 0, "#"),
        (None, None, "+0.00"),
    ],
)
def test_format_eval(cp: int | None, mate: int | None, text: str) -> None:
    assert format_eval(cp, mate) == text


def test_only_explained_moves_get_facts() -> None:
    explained = [move.san for move in opera_moves() if move_facts(move) is not None]

    assert "Nf6" in explained  # mistake
    assert "Bxf3" in explained  # inaccuracy
    assert "Rxd7" in explained  # brilliant
    assert "Qb3" in explained  # great
    assert "e4" not in explained  # book
    assert "d4" not in explained
    plies = {move.ply for move in opera_moves() if move_facts(move) is not None}
    assert all(is_explained(move) == (move.ply in plies) for move in opera_moves())


def test_mistake_facts() -> None:
    facts = move_facts(opera_move("Nf6"))

    assert facts == {
        "move_number": 6,
        "color": "black",
        "move_san": "Nf6",
        "class": "mistake",
        "is_miss": False,
        "eval_before": "-1.31",
        "eval_after": "-2.63",
        "win_chance_drop": 11,
        "phase": "middlegame",
        "best_move_san": "Qf6",
        "best_line_san": ["Qf6", "Qb3", "Nd7", "Qxb7", "Rb8", "Qa6"],
        "refutation_line_san": ["Qb3", "Bc5", "Bxf7+", "Ke7", "Bg5", "Nc6"],
        "material_swing": "-1",
    }


def test_refutation_motifs_are_included() -> None:
    facts = move_facts(opera_move("Qe7"))

    assert facts is not None
    (motif,) = facts["motifs_in_refutation"]
    assert motif["type"] == "trapped_piece"
    assert motif["piece"] == "Q"
    assert motif["square"] == "b7"
    assert motif["targets"] == ["Ra8"]
    assert motif["line_san"][0] == "Qxb7"


def test_brilliant_has_sacrifice_and_no_better_move() -> None:
    rxd7 = move_facts(opera_move("Rxd7"))
    # Почти лучший ход (Δ ≤ 2): лучший формально другой, но «лучше было» не подсказываем.
    qb8 = move_facts(opera_move("Qb8+"))

    assert rxd7 is not None
    assert qb8 is not None
    assert rxd7["class"] == "brilliant"
    assert rxd7["sacrifice"] == {"squares": ["d7"], "material": 2}
    assert opera_move("Qb8+").best_san != "Qb8+"
    assert "best_move_san" not in qb8
    assert "motifs_missed" not in qb8
    assert "refutation_line_san" not in rxd7
    assert any(motif["type"] == "mate_in_n" for motif in qb8["motifs_played"])


def test_miss_flag_gives_best_move() -> None:
    move = replace(opera_move("Qb3"), is_miss=True, move_class=MoveClass.GOOD, best_san="Qe2")

    facts = move_facts(move)

    assert facts is not None
    assert facts["is_miss"] is True
    assert facts["best_move_san"] == "Qe2"
    # Опровержение и потеря материала — только у неточностей и ошибок.
    assert "refutation_line_san" not in facts


def test_motif_facts_conversion() -> None:
    fork = {
        "type": "fork",
        "squares": ["e7", "g8", "c8"],
        "pieces": ["N", "k", "r"],
        "gain_cp": 500,
        "line": [{"uci": "f5e7", "san": "Ne7+"}, {"uci": "g8h8", "san": "Kh8"}],
    }
    mate = {
        "type": "mate_in_n",
        "squares": ["d1"],
        "pieces": ["R"],
        "gain_cp": None,
        "line": [
            {"uci": "a", "san": "Qb8+"},
            {"uci": "b", "san": "Nxb8"},
            {"uci": "c", "san": "Rd8#"},
        ],
    }
    threat: dict[str, Any] = {
        "type": "mate_threat",
        "squares": [],
        "pieces": [],
        "gain_cp": None,
        "line": [],
    }

    assert motif_facts(fork) == {
        "type": "fork",
        "piece": "N",
        "square": "e7",
        "targets": ["Kg8", "Rc8"],
        "material_gain": 5,
        "line_san": ["Ne7+", "Kh8"],
    }
    assert motif_facts(mate)["n"] == 2
    assert "targets" not in motif_facts(mate)
    assert motif_facts(threat) == {"type": "mate_threat"}


def test_material_swing_stops_at_illegal_move() -> None:
    fen = "4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1"
    # Ферзь белых меняется на ферзя чёрных: баланс не меняется.
    trade = [{"uci": "d5d1", "san": "Qxd1"}]
    hang = [{"uci": "d5d1", "san": "Qxd1+"}, {"uci": "a1a2", "san": "??"}]

    assert material_swing(fen, "e1f2", trade) == -9
    assert material_swing(fen, "d1d5", []) == 9
    assert material_swing(fen, "e1f2", hang) == -9


def test_game_facts() -> None:
    facts = game_facts(opera_info(), opera_moves())

    assert facts["result"] == "1-0"
    assert facts["user_color"] == "black"
    assert facts["moves"] == 17
    black = facts["players"]["black"]
    assert black["errors"] == {"inaccuracy": 3, "mistake": 2, "blunder": 0}
    assert black["accuracy"] == round(opera_info().black_accuracy or 0, 1)
    assert set(black["phase_accuracy"]) == {"opening", "middlegame"}
    assert black["typical_errors"] == [{"type": "trapped_piece", "count": 1}]
    assert facts["players"]["white"]["errors"] == {"inaccuracy": 0, "mistake": 0, "blunder": 0}
    # Ключевые моменты — ошибки по порядку партии, не падения оценки у лучших ходов.
    assert [moment["move_san"] for moment in facts["key_moments"]] == ["Nf6", "b5"]
    assert facts["key_moments"][0]["best_move_san"] == "Qf6"


def test_game_facts_without_accuracy() -> None:
    info = replace(opera_info(None), white_accuracy=None, phase_accuracy=None)

    facts = game_facts(info, [])

    assert facts["players"]["white"]["accuracy"] is None
    assert facts["players"]["white"]["phase_accuracy"] == {}
    assert facts["key_moments"] == []


def test_facts_hash_is_canonical() -> None:
    a = {"x": 1, "y": ["Nf3"]}
    b = {"y": ["Nf3"], "x": 1}

    assert facts_hash(a) == facts_hash(b)
    assert facts_hash(a, salt="v1:gemini") != facts_hash(a, salt="v2:gemini")
    assert len(facts_hash(a)) == 64


def test_grounded_tokens_collect_all_strings() -> None:
    facts = move_facts(opera_move("Qe7"))

    assert facts is not None
    tokens = grounded_tokens(facts)
    assert {"Qe7", "Bc5", "Qxb7", "Ra8", "b7"} <= tokens
