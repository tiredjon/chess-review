"""Дерево репертуара и список дебютов из партий одного цвета (чистая логика, без БД).

Партии разбирает `service.py`; здесь на входе уже ходы UCI, результат и дата. Дерево строится
по последовательности ходов от начальной позиции: одна позиция, достигнутая разными порядками
ходов, — разные узлы (в узле — путь). Книга и названия — из `review/openings.py`.
"""

import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import chess

from app.repertoire.types import Mover, RepertoireNode, RepertoireOpening, RepertoireTree
from app.review.openings import OpeningsDB, default_openings

Outcome = Literal["win", "draw", "loss"]
ColorName = Literal["white", "black"]

# Сколько первых полуходов партии хранится: хватает на `max_ply` ≤ 40 и на выход из книги.
STORED_PLIES = 60

_WHITE_OUTCOME: dict[str, Outcome] = {"1-0": "win", "1/2-1/2": "draw", "0-1": "loss"}
_BLACK_OUTCOME: dict[str, Outcome] = {"1-0": "loss", "1/2-1/2": "draw", "0-1": "win"}


def outcome(color: ColorName, result: str) -> Outcome | None:
    """Результат партии с точки зрения игрока цвета `color`; None — партия не окончена."""
    return (_WHITE_OUTCOME if color == "white" else _BLACK_OUTCOME).get(result)


@dataclass(frozen=True, slots=True)
class RepertoireGame:
    """Партия пользователя в виде, нужном репертуару."""

    moves: tuple[str, ...]  # UCI, не больше STORED_PLIES
    outcome: Outcome
    played_at: datetime | None = None
    # Дебют партии (`games.opening_name`) и полуходов до позиции с этим названием.
    opening_name: str | None = None
    opening_eco: str | None = None
    opening_ply: int | None = None
    # Первые подряд книжные полуходы (`OpeningsDB.book_plies`).
    book_plies: int = 0


def game_line(
    moves: Sequence[chess.Move],
    color: ColorName,
    result: str,
    played_at: datetime | None,
    *,
    opening_name: str | None = None,
    opening_eco: str | None = None,
    book: OpeningsDB | None = None,
) -> RepertoireGame | None:
    """Партия для репертуара; None — результат не определён («*»)."""
    result_outcome = outcome(color, result)
    if result_outcome is None:
        return None
    book = book or default_openings()
    kept = moves[:STORED_PLIES]
    board = chess.Board()
    in_book = True
    book_plies = 0
    opening_ply: int | None = None
    for ply, move in enumerate(kept, start=1):
        board.push(move)
        epd = board.epd()
        if in_book and epd in book.positions:
            book_plies += 1
        else:
            in_book = False
        if epd in book.named:
            opening_ply = ply
    return RepertoireGame(
        moves=tuple(move.uci() for move in kept),
        outcome=result_outcome,
        played_at=played_at,
        opening_name=opening_name,
        opening_eco=opening_eco,
        opening_ply=opening_ply,
        book_plies=book_plies,
    )


@dataclass(slots=True)
class _Stats:
    wins: int = 0
    draws: int = 0
    losses: int = 0
    last_played_at: datetime | None = None

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses

    def add(self, game: RepertoireGame) -> None:
        if game.outcome == "win":
            self.wins += 1
        elif game.outcome == "draw":
            self.draws += 1
        else:
            self.losses += 1
        if game.played_at is not None and (
            self.last_played_at is None or game.played_at > self.last_played_at
        ):
            self.last_played_at = game.played_at


@dataclass(slots=True)
class _Trie(_Stats):
    children: dict[str, "_Trie"] = field(default_factory=dict)


def build_tree(
    games: Sequence[RepertoireGame],
    color: ColorName,
    *,
    max_ply: int = 24,
    min_games: int = 2,
    book: OpeningsDB | None = None,
) -> RepertoireTree:
    """Дерево ходов партий цвета `color` до `max_ply` полуходов; узлы с `games < min_games`
    отрезаются вместе с поддеревом. `id` — по обходу в ширину, дети — по убыванию числа партий,
    при равенстве по UCI (для одних данных `id` одни и те же)."""
    if not games:
        return RepertoireTree(color=color, total_games=0, nodes=[])
    book = book or default_openings()
    root = _Trie()
    for game in games:
        node = root
        node.add(game)
        for uci in game.moves[:max_ply]:
            node = node.children.setdefault(uci, _Trie())
            node.add(game)

    learner_parity = 1 if color == "white" else 0  # у белых ходы с нечётных полуходов
    nodes: list[RepertoireNode] = []
    queue: list[_Pending] = [_Pending(root, chess.Board(), None, None, None, None)]
    head = 0
    while head < len(queue):
        item = queue[head]
        head += 1
        board, trie = item.board, item.trie
        node_id = len(nodes)
        ply = len(board.move_stack)
        epd = board.epd()
        opening = book.named.get(epd)
        nodes.append(
            RepertoireNode(
                id=node_id,
                parent=item.parent,
                ply=ply,
                uci=item.uci,
                san=item.san,
                mover=item.mover,
                fen=board.fen(),
                book=ply == 0 or epd in book.positions,
                name=opening.name if opening else None,
                games=trie.games,
                wins=trie.wins,
                draws=trie.draws,
                losses=trie.losses,
                last_played_at=trie.last_played_at,
            )
        )
        if item.parent is not None:
            nodes[item.parent].children.append(node_id)
        kept = [(uci, child) for uci, child in trie.children.items() if child.games >= min_games]
        for uci, child in sorted(kept, key=lambda pair: (-pair[1].games, pair[0])):
            move = chess.Move.from_uci(uci)
            san = board.san(move)
            child_board = board.copy()
            child_board.push(move)
            mover: Mover = "learner" if child_board.ply() % 2 == learner_parity else "opponent"
            queue.append(_Pending(child, child_board, node_id, uci, san, mover))
    return RepertoireTree(color=color, total_games=root.games, nodes=nodes)


@dataclass(slots=True)
class _Pending:
    """Узел в очереди обхода: ещё не превращён в `RepertoireNode`."""

    trie: _Trie
    board: chess.Board
    parent: int | None
    uci: str | None
    san: str | None
    mover: Mover | None


def opening_list(games: Sequence[RepertoireGame]) -> list[RepertoireOpening]:
    """Дебюты по `opening_name`: результат, частый путь, медиана выхода из книги.
    По убыванию числа партий, при равенстве — по названию."""
    groups: dict[str, list[RepertoireGame]] = {}
    for game in games:
        if game.opening_name:
            groups.setdefault(game.opening_name, []).append(game)
    result: list[RepertoireOpening] = []
    for name, group in groups.items():
        stats = _Stats()
        for game in group:
            stats.add(game)
        paths = Counter(
            game.moves[: game.opening_ply] for game in group if game.opening_ply is not None
        )
        line = min(paths, key=lambda path: (-paths[path], path)) if paths else ()
        ecos = Counter(game.opening_eco for game in group if game.opening_eco)
        eco = min(ecos, key=lambda value: (-ecos[value], value)) if ecos else None
        result.append(
            RepertoireOpening(
                name=name,
                eco=eco,
                games=stats.games,
                wins=stats.wins,
                draws=stats.draws,
                losses=stats.losses,
                line_uci=list(line),
                book_exit_ply=statistics.median_low(game.book_plies for game in group),
                last_played_at=stats.last_played_at,
            )
        )
    return sorted(result, key=lambda item: (-item.games, item.name))
