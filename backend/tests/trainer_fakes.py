"""Общее для тестов тренажёра: маленькое дерево курса и фейковый движок."""

from collections.abc import Collection

import chess
from chess.engine import Cp

from app.courses.types import CourseNode, CourseTree
from app.engine.cache import fen_key
from app.plans.types import Idea, PositionIdeas
from app.review.types import EngineLine, PositionEval

IDEAS = PositionIdeas(ideas=(Idea(key="minority_attack", side="white"),))

# (id, parent, uci, mover, main, ideas?)
_SPEC: list[tuple[int, int | None, str | None, str | None, bool, bool]] = [
    (0, None, None, None, False, False),  # начальная позиция: ход за учеником
    (1, 0, "e2e4", "learner", True, True),  # идеи в узле 1
    (2, 1, "e7e5", "opponent", False, False),  # карточка: Nf3 (основной) или Bc4
    (3, 1, "c7c5", "opponent", False, True),  # карточка: Nf3, идеи в самом узле
    (4, 2, "g1f3", "learner", True, False),
    (5, 2, "f1c4", "learner", False, False),
    (6, 3, "g1f3", "learner", True, False),
]


def build_tree(color: str = "white") -> CourseTree:
    boards: dict[int, chess.Board] = {}
    nodes: list[CourseNode] = []
    for node_id, parent, uci, mover, main, ideas in _SPEC:
        board = chess.Board() if parent is None else boards[parent].copy()
        san = None
        if uci is not None:
            move = chess.Move.from_uci(uci)
            san = board.san(move)
            board.push(move)
        boards[node_id] = board
        nodes.append(
            CourseNode(
                id=node_id,
                parent=parent,
                children=[n[0] for n in _SPEC if n[1] == node_id],
                ply=len(board.move_stack),
                uci=uci,
                san=san,
                mover=mover,
                fen=board.fen(),
                book=True,
                main=main,
                ideas=IDEAS if ideas else None,
            )
        )
    return CourseTree(color=color, line_end=1, nodes=nodes)


class ScriptedEngine:
    """Оценка позиции — из словаря «ключ FEN → сантипешки стороне на ходу» (по умолчанию 0)."""

    def __init__(self, scores: dict[str, int] | None = None) -> None:
        self.scores = scores or {}
        self.calls = 0

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        exclude: Collection[chess.Move] = (),
    ) -> PositionEval:
        self.calls += 1
        score = Cp(self.scores.get(fen_key(board), 0))
        move = next(iter(board.legal_moves))
        return PositionEval(score=score, lines=(EngineLine(score=score, pv=(move,)),), depth=depth)


class BrokenEngine:
    async def analyse(self, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError("stockfish")
