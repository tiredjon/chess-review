"""Чистая логика тренажёра: карточки, путь, идеи, вердикты, SRS."""

from datetime import UTC, datetime, timedelta

import chess
import pytest
from chess.engine import Cp, Mate

from app.engine.cache import MemoryEvalCache
from app.review.winprob import win_percent_from_cp
from app.trainer.cards import card_nodes, expected_moves, ideas_node_id, node_path, path_uci
from app.trainer.check import (
    Evaluator,
    IllegalMoveError,
    classify_answer,
    parse_move,
    win_loss,
)
from app.trainer.srs import review_after
from tests.trainer_fakes import ScriptedEngine, build_tree

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def test_card_nodes_are_positions_before_learner_move() -> None:
    tree = build_tree()

    assert [n.id for n in card_nodes(tree)] == [0, 2, 3]
    # Лист и узлы с ходом соперника в детях — не карточки.
    assert 4 not in {n.id for n in card_nodes(tree)}
    assert 1 not in {n.id for n in card_nodes(tree)}


def test_path_and_expected_moves() -> None:
    tree = build_tree()
    node = next(n for n in tree.nodes if n.id == 2)

    assert path_uci(tree, 0) == []
    assert path_uci(tree, 2) == ["e2e4", "e7e5"]
    assert [n.id for n in node_path(tree, 6)] == [0, 1, 3, 6]
    assert node_path(tree, 99) == []
    # Основной ход курса — первым.
    assert [(e.uci, e.san) for e in expected_moves(tree, node)] == [
        ("g1f3", "Nf3"),
        ("f1c4", "Bc4"),
    ]


def test_ideas_node_is_nearest_on_path() -> None:
    tree = build_tree()

    assert ideas_node_id(tree, 3) == 3  # сам узел
    assert ideas_node_id(tree, 2) == 1  # предок
    assert ideas_node_id(tree, 0) is None  # на пути идей нет
    assert ideas_node_id(tree, 99) is None


def test_empty_ideas_are_ignored() -> None:
    tree = build_tree()
    tree.nodes[1].ideas = tree.nodes[1].ideas.model_copy(update={"ideas": ()})  # type: ignore[union-attr]

    assert ideas_node_id(tree, 2) is None


def test_win_loss_is_from_learner_view() -> None:
    # Ученик +100, после хода у соперника −100 (то же самое) — потери нет.
    assert win_loss(Cp(100), Cp(-100)) == pytest.approx(0)
    # Ход ухудшил позицию до равной: потеря = win%(+100) − 50.
    assert win_loss(Cp(100), Cp(0)) == pytest.approx(win_percent_from_cp(100) - 50)
    # Ход «лучше лучшего» (глубины разные) — не отрицательная потеря.
    assert win_loss(Cp(0), Cp(-200)) == 0
    # Мат ученику был, после хода мат пропал — большая потеря.
    assert win_loss(Mate(2), Cp(0)) > 40


def test_threshold_boundary_is_inclusive() -> None:
    assert classify_answer(in_course=True, loss=None, threshold=5) == "main"
    assert classify_answer(in_course=False, loss=5.0, threshold=5) == "alternative"
    assert classify_answer(in_course=False, loss=0.0, threshold=5) == "alternative"
    assert classify_answer(in_course=False, loss=5.0001, threshold=5) == "wrong"
    with pytest.raises(ValueError, match="потер"):
        classify_answer(in_course=False, loss=None, threshold=5)


def test_parse_move_rejects_illegal() -> None:
    board = chess.Board()

    assert parse_move(board, "e2e4") == chess.Move.from_uci("e2e4")
    for bad in ("e2e5", "zzzz", "e7e5"):
        with pytest.raises(IllegalMoveError):
            parse_move(board, bad)


async def test_evaluator_caches_and_skips_terminal() -> None:
    engine = ScriptedEngine()
    cache = MemoryEvalCache()
    evaluator = Evaluator(engine, cache, depth=12)
    board = chess.Board()

    await evaluator.evaluate(board)
    await evaluator.evaluate(board)
    assert engine.calls == 1

    mated = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert (await evaluator.evaluate(mated)).lines == ()
    assert engine.calls == 1


async def test_evaluator_loss_of_uses_both_positions() -> None:
    board = chess.Board()
    after = board.copy()
    after.push_uci("a2a3")
    engine = ScriptedEngine({board.epd(): 50, after.epd(): -20})  # после хода +20 у ученика

    loss = await Evaluator(engine, MemoryEvalCache(), 12).loss_of(
        board, chess.Move.from_uci("a2a3")
    )

    assert loss == pytest.approx(win_percent_from_cp(50) - win_percent_from_cp(20))


def test_srs_transitions() -> None:
    day = timedelta(days=1)

    main = review_after(2, "main", hint_used=False, now=NOW)
    assert (main.box, main.next_review_at) == (3, NOW + timedelta(days=7))
    # Альтернатива — как решение с подсказкой: коробка не растёт, но не ниже 1.
    alt = review_after(2, "alternative", hint_used=False, now=NOW)
    assert alt.box == 2
    assert review_after(0, "alternative", hint_used=False, now=NOW).box == 1
    assert review_after(0, "alternative", hint_used=False, now=NOW).next_review_at == NOW + day
    # Подсказка делает и ход курса «с подсказкой».
    assert review_after(2, "main", hint_used=True, now=NOW).box == 2
    wrong = review_after(4, "wrong", hint_used=False, now=NOW)
    assert (wrong.box, wrong.next_review_at) == (0, NOW + timedelta(minutes=10))
    # Верхняя граница коробок.
    assert review_after(5, "main", hint_used=False, now=NOW).box == 5
