"""Оценки позиций, посчитанные не сервером: Stockfish WASM в браузере (сессия 11).

Браузер повторяет схему `Analyzer` (MultiPV=1, а где сыгран лучший ход — ещё линии
поиском без него) и присылает оценки в формате кэша `position_evals`
(`eval_to_data`). Здесь они проверяются и превращаются в `PositionEval`, дальше —
обычный `review_game`. Финальные позиции сервер оценивает сам (`terminal_eval`),
присланное для них игнорируется.

Данным клиента не доверяем настолько, насколько они могут сломать разбор: ходы линий
должны быть легальны, первые ходы линий — различны. Подделать оценки своей же партии
пользователь может — это влияет только на его разбор, в общий кэш оценок они не пишутся.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import chess
from chess.engine import Cp, Mate, Score

from app.engine.cache import fen_key
from app.review.evaluate import terminal_eval
from app.review.types import EngineLine, PositionEval

MAX_LINES = 5
MAX_PV = 64
# Оценки сильнее этого — уже «выигрыш», точнее cp для разбора не нужен.
MAX_CP = 100_000


class ExternalEvalError(ValueError):
    """Оценка не годится: `index` — номер позиции (полуход) или пробы пазла."""

    def __init__(self, index: int, reason: str) -> None:
        super().__init__(f"позиция {index}: {reason}")
        self.index = index
        self.reason = reason


def _score(index: int, line: Mapping[str, Any]) -> Score:
    cp, mate = line.get("cp"), line.get("mate")
    if (cp is None) == (mate is None):
        raise ExternalEvalError(index, "нужна ровно одна оценка: cp или mate")
    if mate is not None:
        if mate == 0:
            raise ExternalEvalError(index, "mate 0 — это финальная позиция")
        return Mate(int(mate))
    assert cp is not None
    if abs(cp) > MAX_CP:
        raise ExternalEvalError(index, "cp вне диапазона")
    return Cp(int(cp))


def _pv(index: int, board: chess.Board, ucis: Sequence[str]) -> tuple[chess.Move, ...]:
    if not ucis:
        raise ExternalEvalError(index, "пустая линия")
    if len(ucis) > MAX_PV:
        raise ExternalEvalError(index, "слишком длинная линия")
    work = board.copy(stack=False)
    moves = []
    for uci in ucis:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise ExternalEvalError(index, f"некорректный ход {uci}") from exc
        if not work.is_legal(move):
            raise ExternalEvalError(index, f"нелегальный ход {uci} в линии")
        moves.append(move)
        work.push(move)
    return tuple(moves)


def parse_external_eval(index: int, board: chess.Board, data: Mapping[str, Any]) -> PositionEval:
    """`{"depth": 18, "lines": [{"cp": 35 | "mate": 3, "pv": ["e2e4", ...]}, ...]}` →
    `PositionEval` (оценки — за сторону на ходу, как в UCI)."""
    raw_lines = data.get("lines") or []
    if not raw_lines or len(raw_lines) > MAX_LINES:
        raise ExternalEvalError(index, f"линий должно быть от 1 до {MAX_LINES}")
    lines = tuple(
        EngineLine(score=_score(index, line), pv=_pv(index, board, line.get("pv") or []))
        for line in raw_lines
    )
    if len({line.pv[0] for line in lines}) != len(lines):
        raise ExternalEvalError(index, "линии начинаются одним ходом")
    return PositionEval(score=lines[0].score, lines=lines, depth=int(data.get("depth") or 0))


def game_evals(
    positions: Sequence[chess.Board], data: Sequence[Mapping[str, Any] | None]
) -> list[PositionEval]:
    """Оценки всех позиций партии: финальные — свои, остальные — из `data` (по индексу)."""
    if len(data) != len(positions):
        raise ExternalEvalError(len(data), f"нужно {len(positions)} позиций")
    evals = []
    for index, (board, item) in enumerate(zip(positions, data, strict=True)):
        terminal = terminal_eval(board)
        if terminal is not None:
            evals.append(terminal)
        elif item is None:
            raise ExternalEvalError(index, "нет оценки")
        else:
            evals.append(parse_external_eval(index, board, item))
    return evals


@dataclass(frozen=True, slots=True)
class Probe:
    """Позиция, которую генерация пазла проверит движком: MultiPV=2 при сыгранном `move`
    (`PositionAnalyser.analyse(board, multipv=2, played=(move,))`)."""

    fen: str
    move: str


class RecordingAnalyser:
    """Собирает позиции, которые запросит генерация пазлов, отвечая «ход единственный» —
    так проверка доходит до конца каждого решения и запрашивает все его позиции."""

    def __init__(self) -> None:
        self.probes: dict[tuple[str, str], Probe] = {}

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        played: Collection[chess.Move] = (),
    ) -> PositionEval:
        step = next(iter(played))
        self.probes.setdefault((fen_key(board), step.uci()), Probe(board.fen(), step.uci()))
        other = next((move for move in board.legal_moves if move != step), None)
        lines = [EngineLine(score=Cp(MAX_CP), pv=(step,))]
        if other is not None:
            lines.append(EngineLine(score=Cp(-MAX_CP), pv=(other,)))
        return PositionEval(score=lines[0].score, lines=tuple(lines), depth=depth)


class ProbeAnalyser:
    """Ответы на пробы, посчитанные браузером; позиции без ответа — без линий (пазл
    из такой ошибки просто не получится)."""

    def __init__(self, evals: Mapping[tuple[str, str], PositionEval]) -> None:
        self.evals = evals

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        played: Collection[chess.Move] = (),
    ) -> PositionEval:
        step = next(iter(played), None)
        found = None if step is None else self.evals.get((fen_key(board), step.uci()))
        return found if found is not None else PositionEval(score=Cp(0))
