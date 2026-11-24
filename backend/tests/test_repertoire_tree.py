"""Репертуар: дерево ходов и список дебютов на фиксированных партиях (без БД)."""

from datetime import UTC, datetime

import chess

from app.repertoire.tree import (
    RepertoireGame,
    build_tree,
    game_line,
    opening_list,
    outcome,
)
from app.repertoire.types import RepertoireNode


def moves(san: str) -> list[chess.Move]:
    board = chess.Board()
    result = []
    for token in san.split():
        move = board.parse_san(token)
        result.append(move)
        board.push(move)
    return result


def day(n: int) -> datetime:
    return datetime(2026, 1, n, tzinfo=UTC)


def line(
    san: str,
    color: str,
    result: str,
    n: int = 1,
    *,
    name: str | None = None,
    eco: str | None = None,
) -> RepertoireGame:
    game = game_line(
        moves(san),
        color,  # type: ignore[arg-type]
        result,
        day(n),
        opening_name=name,
        opening_eco=eco,
    )
    assert game is not None
    return game


def by_path(nodes: list[RepertoireNode], san: str) -> RepertoireNode:
    """Узел по пути из SAN от корня."""
    node = nodes[0]
    for token in san.split():
        node = next(nodes[i] for i in node.children if nodes[i].san == token)
    return node


WHITE = [
    line("e4 e5 Nf3 Nc6 Bb5", "white", "1-0", 1),
    line("e4 e5 Nf3 Nc6 Bc4", "white", "0-1", 2),
    line("e4 e5 Nf3 Nf6", "white", "1/2-1/2", 3),
    line("e4 c5", "white", "1-0", 4),
    line("d4 d5 Nf3", "white", "1-0", 5),
    line("Nf3 d5 d4", "white", "0-1", 6),
]


def test_outcome_from_user_point_of_view() -> None:
    assert outcome("white", "1-0") == "win"
    assert outcome("black", "1-0") == "loss"
    assert outcome("black", "0-1") == "win"
    assert outcome("black", "1/2-1/2") == "draw"
    assert outcome("white", "*") is None
    assert game_line(moves("e4"), "white", "*", None) is None


def test_tree_counts_results_and_mover_for_white() -> None:
    tree = build_tree(WHITE, "white", min_games=1)
    nodes = tree.nodes

    assert tree.total_games == 6
    root = nodes[0]
    assert (root.id, root.parent, root.ply, root.uci, root.san, root.mover) == (
        0,
        None,
        0,
        None,
        None,
        None,
    )
    assert (root.games, root.wins, root.draws, root.losses) == (6, 3, 1, 2)
    assert root.book is True

    e4 = by_path(nodes, "e4")
    assert (e4.games, e4.wins, e4.draws, e4.losses) == (4, 2, 1, 1)
    assert e4.mover == "learner"
    assert (e4.ply, e4.uci) == (1, "e2e4")
    assert e4.last_played_at == day(4)
    assert by_path(nodes, "e4 e5").mover == "opponent"
    assert by_path(nodes, "e4 e5 Nf3").mover == "learner"
    nc6 = by_path(nodes, "e4 e5 Nf3 Nc6")
    assert (nc6.games, nc6.wins, nc6.losses) == (2, 1, 1)
    # Родитель и дети согласованы.
    assert all(nodes[c].parent == n.id for n in nodes for c in n.children)


def test_tree_mover_and_results_for_black() -> None:
    games = [
        line("e4 c5 Nf3", "black", "0-1", 1),
        line("e4 c5 Nf3", "black", "1-0", 2),
        line("e4 e5", "black", "1/2-1/2", 3),
    ]
    nodes = build_tree(games, "black", min_games=1).nodes

    assert by_path(nodes, "e4").mover == "opponent"
    c5 = by_path(nodes, "e4 c5")
    assert c5.mover == "learner"
    assert (c5.games, c5.wins, c5.draws, c5.losses) == (2, 1, 0, 1)
    assert (nodes[0].wins, nodes[0].draws, nodes[0].losses) == (1, 1, 1)


def test_min_games_cuts_subtree() -> None:
    nodes = build_tree(WHITE, "white", min_games=2).nodes

    # Bb5 / Bc4 / Nf6 / c5 и ветки d4 / Nf3 — по одной партии: отрезаны.
    assert [n.san for n in nodes] == [None, "e4", "e5", "Nf3", "Nc6"]
    assert by_path(nodes, "e4 e5 Nf3 Nc6").children == []
    assert all(n.games >= 2 for n in nodes[1:])
    # Узел, который сам прошёл порог, но чей родитель — нет, не появляется.
    assert len(nodes) == 5  # root, e4, e5, Nf3, Nc6


def test_max_ply_cuts_depth() -> None:
    nodes = build_tree(WHITE, "white", max_ply=3, min_games=1).nodes
    assert max(n.ply for n in nodes) == 3
    assert not any(n.san == "Nc6" for n in nodes)


def test_transpositions_are_not_merged() -> None:
    nodes = build_tree(WHITE, "white", min_games=1).nodes
    a = by_path(nodes, "d4 d5 Nf3")
    b = by_path(nodes, "Nf3 d5 d4")
    assert a.id != b.id
    assert a.fen.split()[:4] == b.fen.split()[:4]
    assert (a.games, b.games) == (1, 1)


def test_ids_order_and_stability() -> None:
    nodes = build_tree(WHITE, "white", min_games=1).nodes
    # Дети корня: e4 (4 партии), затем d4 и Nf3 (по 1) — по UCI: d2d4 < g1f3.
    assert [nodes[i].san for i in nodes[0].children] == ["e4", "d4", "Nf3"]
    # id идут по обходу в ширину: глубина не убывает.
    assert [n.ply for n in nodes] == sorted(n.ply for n in nodes)
    assert [n.id for n in nodes] == list(range(len(nodes)))
    # Внутри e4: e5 (3) раньше c5 (1).
    assert [nodes[i].san for i in by_path(nodes, "e4").children] == ["e5", "c5"]

    again = build_tree(list(reversed(WHITE)), "white", min_games=1).nodes
    assert [(n.id, n.uci, n.games) for n in again] == [(n.id, n.uci, n.games) for n in nodes]


def test_book_and_names() -> None:
    nodes = build_tree(WHITE, "white", min_games=1).nodes
    ruy = by_path(nodes, "e4 e5 Nf3 Nc6 Bb5")
    assert ruy.book is True
    assert ruy.name is not None
    assert "Ruy Lopez" in ruy.name
    assert by_path(nodes, "e4").book is True
    far = build_tree(
        [line("a3 a6 b3 b6 c3 c6 d3 d6 e3 e6", "white", "1-0")], "white", min_games=1
    ).nodes
    assert far[-1].book is False
    assert far[-1].name is None


def test_empty_repertoire() -> None:
    tree = build_tree([], "white")
    assert tree.total_games == 0
    assert tree.nodes == []


def test_openings_list() -> None:
    games = [
        line(
            "e4 e5 Nf3 Nc6 Bb5 a6", "white", "1-0", 1, name="Ruy Lopez: Morphy Defense", eco="C78"
        ),
        line(
            "e4 e5 Nf3 Nc6 Bb5 a6", "white", "0-1", 3, name="Ruy Lopez: Morphy Defense", eco="C78"
        ),
        line(
            "e4 e5 Nf3 Nc6 Bb5 a6",
            "white",
            "1/2-1/2",
            2,
            name="Ruy Lopez: Morphy Defense",
            eco="C78",
        ),
        line("d4 d5 c4", "white", "1-0", 4, name="Queen's Gambit", eco="D06"),
        line("a3", "white", "1-0", 5),  # без названия — не в списке
    ]
    result = opening_list(games)

    assert [o.name for o in result] == ["Ruy Lopez: Morphy Defense", "Queen's Gambit"]
    ruy = result[0]
    assert (ruy.eco, ruy.games, ruy.wins, ruy.draws, ruy.losses) == ("C78", 3, 1, 1, 1)
    assert ruy.last_played_at == day(3)
    assert ruy.line_uci == ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"]
    assert ruy.book_exit_ply >= 6


def test_openings_frequent_path_and_median_book_exit() -> None:
    name = "Italian Game"
    a = line("e4 e5 Nf3 Nc6 Bc4", "white", "1-0", 1, name=name)
    b = line("Nf3 Nc6 e4 e5 Bc4", "white", "1-0", 2, name=name)  # переход в ту же позицию
    games = [a, a, b]
    (item,) = opening_list(games)
    assert item.games == 3
    assert item.line_uci == list(a.moves[:5])

    def with_book(game: RepertoireGame, plies: int) -> RepertoireGame:
        return RepertoireGame(
            game.moves, game.outcome, game.played_at, game.opening_name, None, 5, plies
        )

    (median,) = opening_list([with_book(a, 4), with_book(a, 10), with_book(a, 6)])
    assert median.book_exit_ply == 6
    (low,) = opening_list([with_book(a, 4), with_book(a, 10)])
    assert low.book_exit_ply == 4
