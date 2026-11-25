"""Сборщик дерева курса (`CourseTree`, `types.py`): исходная линия от начальной позиции и
продолжения дальше теории по партиям мастеров, проверенные движком.

Чистая логика: Opening Explorer, движок, кэш оценок, база дебютов и идеи позиции приходят
снаружи (в воркере — Lichess через кэш в БД и пул Stockfish, в тестах — фейки).

Как растёт дерево:
- Исходная линия — одна цепочка узлов (ответвлений до её конца нет). Курс идёт до
  `target_plies` полуходов (но не меньше чем на `MIN_BEYOND_PLIES` дальше линии) и не больше
  `max_nodes` узлов.
- Ход за ученика — один: самый популярный у мастеров ход, если движок считает его не хуже
  лучшего больше чем на `alt_threshold` пунктов win% (тот же порог, что засчитывает
  альтернативу в тренажёре); не прошёл — следующий популярный (до `LEARNER_CANDIDATES`,
  с долей не меньше `min_share`); не прошёл никто — лучший ход движка.
- За соперника — до `opponent_branches` ответов мастеров с долей не меньше `min_share`
  (`weight` = доля); если таких нет — самый популярный ответ.
- Позиция, где у мастеров меньше `MIN_MASTER_GAMES` партий, — только движок (за соперника —
  одна ветка, лучший ход движка).
- Бюджет узлов тратится линиями по убыванию вероятности: берётся самый вероятный ещё не
  раскрытый узел, от него линия ведётся по самому частому ходу до конца, остальные ответы
  соперника встают в очередь. Так каждая линия курса доходит до цели, пока хватает бюджета.

Ключевые узлы (`key_moment`, в них — `ideas`): `book_exit` — первая позиция вне базы
дебютов после книжной; `structure` — появилась новая типовая пешечная структура и держится
после следующего хода; `line_end` — конец исходной линии и концы линий курса (листья).
Образцовые партии — `topGames` мастеров из ключевых узлов, самые глубокие первыми."""

import hashlib
import heapq
import itertools
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

import chess
import structlog
from chess.engine import PovScore

from app.core.config import Settings
from app.courses.types import (
    BUILDER_VERSION,
    CourseNode,
    CourseTree,
    ModelGame,
    Mover,
    MoveStats,
    NodeEval,
)
from app.engine.analyzer import PositionEngine
from app.engine.cache import EvalCache, fen_key
from app.explorer.types import (
    ExplorerMove,
    ExplorerPosition,
    ExplorerSource,
    ExplorerUnavailableError,
    OpeningExplorer,
)
from app.plans.ideas import position_ideas
from app.plans.types import PositionIdeas
from app.review.evaluate import terminal_eval
from app.review.openings import OpeningsDB, default_openings
from app.review.types import PositionEval
from app.review.winprob import win_percent

log = structlog.get_logger(__name__)

# Меньше партий мастеров в позиции — статистика случайна, ходы выбирает движок.
MIN_MASTER_GAMES = 5
# Сколько популярных ходов мастеров проверять движком за ученика.
LEARNER_CANDIDATES = 3
# Курс идёт хотя бы на столько полуходов дальше исходной линии.
MIN_BEYOND_PLIES = 6
# Исходная линия длиннее — 422 `line_invalid` (в базе дебютов самая длинная — 36).
MAX_LINE_PLIES = 60
# Образцовые партии: не больше стольких на ключевой узел и всего.
GAMES_PER_NODE = 2
MAX_MODEL_GAMES = 6

KeyMoment = Literal["book_exit", "structure", "line_end"]
ProgressFn = Callable[[int], Awaitable[None]]
IdeasFn = Callable[[chess.Board], PositionIdeas]


class LineError(ValueError):
    """Исходная линия курса не разбирается или нелегальна; `index` — номер плохого хода."""

    def __init__(self, message: str, index: int | None = None) -> None:
        super().__init__(message)
        self.index = index


def parse_line(line_uci: Sequence[str]) -> list[chess.Move]:
    """Ходы линии от начальной позиции. Рокировка в записи «король берёт ладью» (e1h1)
    приводится к обычной (e1g1), поэтому одна линия — один ключ курса."""
    if not line_uci:
        raise LineError("Пустая линия")
    if len(line_uci) > MAX_LINE_PLIES:
        raise LineError(f"Линия длиннее {MAX_LINE_PLIES} полуходов")
    board = chess.Board()
    moves: list[chess.Move] = []
    for index, uci in enumerate(line_uci):
        try:
            move = board.parse_uci(uci.strip().lower())
        except ValueError as exc:
            message = f"Ход {index + 1} ({uci}) нелегален или записан неверно"
            raise LineError(message, index) from exc
        board.push(move)
        moves.append(move)
    return moves


def course_key(color: chess.Color, line: Sequence[chess.Move]) -> str:
    """Ключ курса: цвет + линия + версия сборщика (sha256, 64 символа)."""
    side = "white" if color == chess.WHITE else "black"
    raw = f"{side}|{' '.join(m.uci() for m in line)}|v{BUILDER_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class BuildLimits:
    target_plies: int = 30
    max_nodes: int = 80
    opponent_branches: int = 3
    min_share: float = 0.1
    engine_depth: int = 16
    alt_threshold: float = 5.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "BuildLimits":
        return cls(
            target_plies=settings.course_target_plies,
            max_nodes=settings.course_max_nodes,
            opponent_branches=settings.course_opponent_branches,
            min_share=settings.course_min_share,
            engine_depth=settings.course_engine_depth,
            alt_threshold=settings.course_alt_threshold,
        )


def win_loss(best: PositionEval, after: PositionEval) -> float:
    """Потеря win% стороной, сделавшей ход: `best` — позиция до хода (глазами ходящего),
    `after` — после хода (глазами соперника). Как `trainer.check.win_loss`."""
    return max(0.0, win_percent(best.score) - (100.0 - win_percent(after.score)))


def node_eval(board: chess.Board, value: PositionEval) -> NodeEval:
    white = PovScore(value.score, board.turn).white()
    best = value.best_move
    return NodeEval(
        cp=white.score() if not white.is_mate() else None,
        mate=white.mate() if white.is_mate() else None,
        depth=value.depth,
        best_uci=best.uci() if best is not None else None,
    )


def _stats(move: ExplorerMove) -> MoveStats:
    return MoveStats(
        source="masters",
        games=move.games,
        white=move.white,
        draws=move.draws,
        black=move.black,
        average_rating=move.average_rating,
    )


# Ответ соперника: ход, доля у мастеров, статистика.
_Reply = tuple[chess.Move, float, MoveStats | None]


@dataclass(slots=True)
class _Draft:
    id: int
    parent: int | None
    board: chess.Board
    move: chess.Move | None
    san: str | None
    mover: Mover | None
    main: bool = False
    weight: float = 1.0
    # Вероятность дойти до узла по ответам соперника (для очереди линий).
    reach: float = 1.0
    stats: MoveStats | None = None
    eval: PositionEval | None = None
    children: list[int] = field(default_factory=list)
    explorer: ExplorerPosition | None = None

    @property
    def ply(self) -> int:
        return len(self.board.move_stack)


class CourseBuilder:
    def __init__(
        self,
        explorer: OpeningExplorer,
        engine: PositionEngine,
        *,
        limits: BuildLimits | None = None,
        cache: EvalCache | None = None,
        openings: OpeningsDB | None = None,
        ideas: IdeasFn = position_ideas,
        progress: ProgressFn | None = None,
    ) -> None:
        self._explorer = explorer
        self._engine = engine
        self._limits = limits or BuildLimits()
        self._cache = cache
        self._openings = openings or default_openings()
        self._ideas = ideas
        self._progress = progress
        self._reported = -1
        self._evals: dict[str, PositionEval] = {}
        self._positions: dict[str, ExplorerPosition | None] = {}
        self._nodes: list[_Draft] = []

    # --- зависимости ---

    async def _report(self, percent: int) -> None:
        percent = max(0, min(100, percent))
        if self._progress is not None and percent > self._reported:
            self._reported = percent
            await self._progress(percent)

    async def _evaluate(self, board: chess.Board) -> PositionEval:
        """Оценка позиции глазами стороны на ходу: финальная — без движка, затем память,
        внешний кэш и движок (MultiPV = 1)."""
        final = terminal_eval(board)
        if final is not None:
            return final
        key = fen_key(board)
        if key in self._evals:
            return self._evals[key]
        depth = self._limits.engine_depth
        value = await self._cache.get(key, depth, 1) if self._cache is not None else None
        if value is None:
            value = await self._engine.analyse(board, depth=depth, multipv=1)
            if self._cache is not None:
                await self._cache.put(key, depth, 1, value)
        self._evals[key] = value
        return value

    async def _masters(self, board: chess.Board) -> ExplorerPosition | None:
        """Позиция у мастеров; None — партий слишком мало (решает движок)."""
        key = board.epd()
        if key not in self._positions:
            position = await self._explorer.position(board, source=ExplorerSource.MASTERS)
            self._positions[key] = position if position.games >= MIN_MASTER_GAMES else None
        return self._positions[key]

    # --- узлы ---

    def _add(
        self,
        parent: _Draft | None,
        move: chess.Move | None,
        *,
        mover: Mover | None,
        main: bool = False,
        weight: float = 1.0,
        stats: MoveStats | None = None,
    ) -> _Draft:
        board = chess.Board() if parent is None else parent.board.copy()
        san = None
        if move is not None:
            san = board.san(move)
            board.push(move)
        node = _Draft(
            id=len(self._nodes),
            parent=parent.id if parent is not None else None,
            board=board,
            move=move,
            san=san,
            mover=mover,
            main=main,
            weight=weight,
            reach=(parent.reach if parent is not None else 1.0) * weight,
            stats=stats,
        )
        self._nodes.append(node)
        if parent is not None:
            parent.children.append(node.id)
        return node

    def _mover(self, board: chess.Board, color: chess.Color) -> Mover:
        """Кто делает следующий ход из позиции `board`."""
        return "learner" if board.turn == color else "opponent"

    # --- выбор ходов ---

    async def _learner_move(self, node: _Draft) -> tuple[chess.Move, MoveStats | None] | None:
        board = node.board
        best = await self._evaluate(board)
        engine_best = best.best_move
        position = await self._masters(board)
        if position is not None:
            for index, candidate in enumerate(position.moves[:LEARNER_CANDIDATES]):
                if index > 0 and candidate.games / position.games < self._limits.min_share:
                    break
                move = chess.Move.from_uci(candidate.uci)
                if not board.is_legal(move):
                    continue
                if move == engine_best:
                    return move, _stats(candidate)
                after = board.copy(stack=False)
                after.push(move)
                if win_loss(best, await self._evaluate(after)) <= self._limits.alt_threshold:
                    return move, _stats(candidate)
        if engine_best is None:
            return None
        stats = None
        if position is not None:
            stats = next((_stats(m) for m in position.moves if m.uci == engine_best.uci()), None)
        return engine_best, stats

    async def _opponent_moves(self, node: _Draft) -> list[_Reply]:
        board = node.board
        position = await self._masters(board)
        if position is not None:
            legal: list[_Reply] = [
                (move, round(m.games / position.games, 4), _stats(m))
                for m in position.moves
                if board.is_legal(move := chess.Move.from_uci(m.uci))
            ]
            replies = [r for r in legal if r[1] >= self._limits.min_share]
            if replies or legal:
                return (replies or legal[:1])[: self._limits.opponent_branches]
        best = (await self._evaluate(board)).best_move
        return [] if best is None else [(best, 1.0, None)]

    async def _expand(self, node: _Draft, color: chess.Color) -> list[_Draft]:
        """Дети узла по правилам выше, не больше остатка бюджета; самый частый — первым."""
        room = self._limits.max_nodes - len(self._nodes)
        if room <= 0 or node.board.is_game_over():
            return []
        mover = self._mover(node.board, color)
        if mover == "learner":
            chosen = await self._learner_move(node)
            if chosen is None:
                return []
            move, stats = chosen
            return [self._add(node, move, mover=mover, main=True, stats=stats)]
        replies = await self._opponent_moves(node)
        return [
            self._add(node, move, mover=mover, weight=weight, stats=stats)
            for move, weight, stats in replies[:room]
        ]

    # --- сборка ---

    async def build(self, line: Sequence[chess.Move], color: chess.Color) -> CourseTree:
        if not line:
            raise LineError("Пустая линия")
        limits = self._limits
        target = max(limits.target_plies, len(line) + MIN_BEYOND_PLIES)
        log_ = log.bind(line=" ".join(m.uci() for m in line), color=chess.COLOR_NAMES[color])
        self._nodes = []
        self._reported = -1

        # Исходная линия: статистика ходов — из позиции до хода.
        node = self._add(None, None, mover=None)
        for index, move in enumerate(line):
            position = await self._masters(node.board)
            stats = None
            weight = 1.0
            if position is not None:
                found = next((m for m in position.moves if m.uci == move.uci()), None)
                if found is not None:
                    stats = _stats(found)
            mover = self._mover(node.board, color)
            if mover == "opponent" and stats is not None and position is not None:
                weight = round(stats.games / position.games, 4)
            node = self._add(
                node, move, mover=mover, main=mover == "learner", weight=weight, stats=stats
            )
            # Вероятность вдоль исходной линии не убывает: это линия, которую выбрали учить.
            node.reach = 1.0
            await self._report(10 * (index + 1) // len(line))
        line_end = node.id

        # Дальше теории — линиями по убыванию вероятности.
        order = itertools.count()
        frontier: list[tuple[float, int, int]] = [(-1.0, next(order), line_end)]
        while frontier and len(self._nodes) < limits.max_nodes:
            _, _, start = heapq.heappop(frontier)
            current = self._nodes[start]
            while current.ply < target:
                children = await self._expand(current, color)
                if not children:
                    break
                for sibling in children[1:]:
                    heapq.heappush(frontier, (-sibling.reach, next(order), sibling.id))
                current = children[0]
                await self._report(10 + 75 * len(self._nodes) // limits.max_nodes)

        for draft in self._nodes:
            draft.eval = await self._evaluate(draft.board)
        await self._report(88)

        nodes = self._finish(line_end)
        await self._report(90)
        games = await self._model_games(nodes)
        log_.info(
            "course.built",
            nodes=len(nodes),
            leaves=sum(1 for n in nodes if not n.children),
            key=sum(1 for n in nodes if n.key_moment),
            games=len(games),
        )
        await self._report(100)
        return CourseTree(
            version=BUILDER_VERSION,
            color="white" if color == chess.WHITE else "black",
            line_end=line_end,
            nodes=nodes,
            model_games=games,
        )

    def _finish(self, line_end: int) -> list[CourseNode]:
        """Книжность, названия, ключевые узлы и идеи; черновики → `CourseNode`."""
        ideas = [self._ideas(draft.board) for draft in self._nodes]
        book = [d.parent is None or self._openings.contains(d.board) for d in self._nodes]

        def structure(index: int) -> str | None:
            found = ideas[index].structures
            return found[0] if found else None

        nodes: list[CourseNode] = []
        for draft in self._nodes:
            reason: KeyMoment | None = None
            parent = draft.parent
            if parent is not None and book[parent] and not book[draft.id]:
                reason = "book_exit"
            elif (
                parent is not None
                and structure(draft.id) is not None
                and structure(draft.id) != structure(parent)
                and all(structure(kid) == structure(draft.id) for kid in draft.children)
            ):
                reason = "structure"
            elif draft.id == line_end or not draft.children:
                reason = "line_end"
            opening = self._openings.lookup(draft.board)
            assert draft.eval is not None
            nodes.append(
                CourseNode(
                    id=draft.id,
                    parent=draft.parent,
                    children=list(draft.children),
                    ply=draft.ply,
                    uci=draft.move.uci() if draft.move is not None else None,
                    san=draft.san,
                    mover=draft.mover,
                    fen=draft.board.fen(),
                    book=book[draft.id],
                    name=opening.name if opening is not None else None,
                    main=draft.main,
                    weight=draft.weight,
                    stats=draft.stats,
                    eval=node_eval(draft.board, draft.eval),
                    ideas=ideas[draft.id] if reason is not None else None,
                    key_moment=reason,
                )
            )
        return nodes

    async def _model_games(self, nodes: list[CourseNode]) -> list[ModelGame]:
        """Партии мастеров из `topGames` ключевых узлов: глубже — раньше. Партия, которую
        не удалось скачать, пропускается (курс без неё всё равно полезен)."""
        keyed = sorted((n for n in nodes if n.key_moment is not None), key=lambda n: (-n.ply, n.id))
        picked: list[tuple[int, str]] = []
        seen: set[str] = set()
        for node in keyed:
            position = self._positions.get(self._nodes[node.id].board.epd())
            if position is None:
                continue
            taken = 0
            for ref in position.top_games:
                if ref.id in seen or taken >= GAMES_PER_NODE:
                    continue
                seen.add(ref.id)
                picked.append((node.id, ref.id))
                taken += 1
            if len(picked) >= MAX_MODEL_GAMES:
                break
        games: list[ModelGame] = []
        for index, (node_id, game_id) in enumerate(picked[:MAX_MODEL_GAMES]):
            try:
                game = await self._explorer.master_game(game_id)
            except ExplorerUnavailableError as exc:
                log.warning("course.model_game_failed", game_id=game_id, error=str(exc))
                continue
            games.append(
                ModelGame(
                    id=game.id,
                    node_id=node_id,
                    white=game.white,
                    black=game.black,
                    white_rating=game.white_rating,
                    black_rating=game.black_rating,
                    year=game.year,
                    result=game.result,
                    pgn=game.pgn,
                )
            )
            await self._report(90 + 10 * (index + 1) // MAX_MODEL_GAMES)
        return games
