"""Пазлы из ошибок пользователя: позиция, решение, однозначность, проверка попытки.

Источник — ход пользователя класса mistake / blunder или с флагом miss. Позиция — до этого
хода, решение — лучшая линия (PV1) до мата или выигрыша материала, ответы соперника —
из той же линии. Если лучшая линия материал не выигрывает (ошибка позиционная или защитная),
пазл — один лучший ход, тема `only_move`. Пазл отбрасывается, если какой-то ход игрока
в решении не единственный (разрыв с 2-й линией MultiPV меньше `PUZZLE_MIN_GAP`): иначе
верный по сути ход считался бы ошибкой. Движок вызывается через протокол, как в
`review/pipeline.py`.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import chess
from chess.engine import Cp, Mate, Score

from app.review.material import material_balance
from app.review.thresholds import PUZZLE_MAX_PLAYER_MOVES, PUZZLE_MIN_GAIN, PUZZLE_MIN_GAP
from app.review.types import EngineLine, MoveClass, PositionEval
from app.review.winprob import win_percent

SOURCE_CLASSES = frozenset({MoveClass.MISTAKE, MoveClass.BLUNDER})
MATE_THEME = "mate_in_n"
ONLY_MOVE_THEME = "only_move"


class PositionAnalyser(Protocol):
    """`app.engine.analyzer.Analyzer.analyse`: при `played` с лучшим ходом — `multipv` линий."""

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        played: Collection[chess.Move] = (),
    ) -> PositionEval: ...


class SourceMove(Protocol):
    """Сохранённый разбор хода — строка `moves` (формат JSON — `workers/serialize.py`)."""

    @property
    def fen_before(self) -> str: ...
    @property
    def uci(self) -> str: ...
    @property
    def move_class(self) -> MoveClass: ...
    @property
    def is_miss(self) -> bool: ...
    @property
    def best_uci(self) -> str | None: ...
    @property
    def pv(self) -> list[Any] | None: ...
    @property
    def multipv(self) -> list[Any] | None: ...
    @property
    def motifs(self) -> dict[str, Any] | None: ...


class PrevMove(Protocol):
    @property
    def fen_before(self) -> str: ...
    @property
    def uci(self) -> str: ...


@dataclass(frozen=True, slots=True)
class PuzzleDraft:
    fen: str
    # Ход игрока, ответ, ход игрока, …; первый и последний — ходы игрока.
    solution: tuple[str, ...]
    themes: tuple[str, ...]


def gives_mate(board: chess.Board, move: chess.Move) -> bool:
    after = board.copy(stack=False)
    after.push(move)
    return after.is_checkmate()


def is_source(move: SourceMove) -> bool:
    return (
        (move.move_class in SOURCE_CLASSES or move.is_miss)
        and move.best_uci is not None
        and move.best_uci != move.uci
        and bool(move.pv)
    )


def parse_line(line: Sequence[Mapping[str, str]] | None) -> list[chess.Move]:
    """Линия из JSON до первого нулевого хода (угроза «любой ход соперника»)."""
    moves = []
    for step in line or []:
        move = chess.Move.from_uci(step["uci"])
        if not move:
            break
        moves.append(move)
    return moves


def parse_lines(multipv: Sequence[Mapping[str, Any]] | None) -> tuple[EngineLine, ...]:
    lines = []
    for line in multipv or []:
        score: Score = Mate(line["mate"]) if line.get("mate") is not None else Cp(line["cp"] or 0)
        lines.append(EngineLine(score=score, pv=tuple(parse_line(line.get("pv")))))
    return tuple(lines)


def baseline_material(board: chess.Board, prev: PrevMove | None) -> int:
    """Материал игрока, от которого считается выигрыш: до последнего хода соперника, если
    он больше. Иначе «отыграть» только что взятую фигуру было бы пазлом."""
    player = board.turn
    current = material_balance(board, player)
    if prev is None:
        return current
    before = chess.Board(prev.fen_before)
    if before.turn == player:
        return current
    return max(current, material_balance(before, player))


def cut_solution(
    board: chess.Board, line: Sequence[chess.Move], baseline: int
) -> list[chess.Move] | None:
    """Начало линии до мата или до хода игрока, после которого (и ответа соперника)
    материал игрока вырос хотя бы на `PUZZLE_MIN_GAIN`. None — не дошли за
    `PUZZLE_MAX_PLAYER_MOVES` ходов игрока, линия кончилась или в ней нелегальный ход."""
    work = board.copy(stack=False)
    player = work.turn
    for index in range(0, min(len(line), 2 * PUZZLE_MAX_PLAYER_MOVES), 2):
        move = line[index]
        if not work.is_legal(move):
            return None
        work.push(move)
        if work.is_checkmate():
            return list(line[: index + 1])
        if index + 1 >= len(line) or not work.is_legal(line[index + 1]):
            return None
        work.push(line[index + 1])
        if material_balance(work, player) - baseline >= PUZZLE_MIN_GAIN:
            return list(line[: index + 1])
    return None


def is_clear_best(board: chess.Board, lines: Sequence[EngineLine]) -> bool:
    """Лучший ход единственный: второй вариант хуже хотя бы на `PUZZLE_MIN_GAP` win%."""
    if board.legal_moves.count() < 2:
        return True
    if len(lines) < 2:
        return False
    return win_percent(lines[0].score) - win_percent(lines[1].score) >= PUZZLE_MIN_GAP


def puzzle_themes(
    motifs: Mapping[str, Any] | None, *, ends_in_mate: bool, only_move: bool
) -> tuple[str, ...]:
    """Темы — мотивы упущенной лучшей линии (`motifs.missed`), без повторов;
    у пазла без выигрыша материала первой идёт `only_move`."""
    themes = list(dict.fromkeys(m["type"] for m in (motifs or {}).get("missed", [])))
    if only_move:
        themes.insert(0, ONLY_MOVE_THEME)
    if ends_in_mate and MATE_THEME not in themes:
        themes.append(MATE_THEME)
    return tuple(themes)


async def build_puzzle(
    move: SourceMove, prev: PrevMove | None, analyser: PositionAnalyser, *, depth: int
) -> PuzzleDraft | None:
    """Пазл из ошибки или None, если ход не подходит или решение неоднозначно."""
    if not is_source(move):
        return None
    board = chess.Board(move.fen_before)
    line = parse_line(move.pv)
    solution = cut_solution(board, line, baseline_material(board, prev))
    only_move = solution is None
    if solution is None:
        solution = line[:1]
        if not solution or not board.is_legal(solution[0]):
            return None

    work = board.copy(stack=False)
    for index, step in enumerate(solution):
        final = index == len(solution) - 1
        # Ходы соперника не проверяются; последний матующий ход — любой мат засчитывается.
        if index % 2 == 0 and not (final and gives_mate(work, step)):
            lines = parse_lines(move.multipv) if index == 0 else ()
            if len(lines) < 2:
                lines = (await analyser.analyse(work, depth=depth, multipv=2, played=(step,))).lines
            if not lines or lines[0].pv[:1] != (step,) or not is_clear_best(work, lines):
                return None
        work.push(step)

    return PuzzleDraft(
        fen=move.fen_before,
        solution=tuple(step.uci() for step in solution),
        themes=puzzle_themes(move.motifs, ends_in_mate=work.is_checkmate(), only_move=only_move),
    )


class AttemptError(ValueError):
    """Попытка не соответствует пазлу (не тот ответ соперника, нелегальный ход…)."""


@dataclass(frozen=True, slots=True)
class AttemptCheck:
    result: Literal["continue", "solved", "failed"]
    # continue: ответ соперника, который нужно сыграть.
    reply: str | None = None
    # failed: верный ход там, где игрок ошибся (или сдался).
    expected: str | None = None


def _same_move(move: chess.Move, expected: chess.Move) -> bool:
    """Превращение с доски — всегда в ферзя, поэтому достаточно клеток «откуда-куда»."""
    return move.from_square == expected.from_square and move.to_square == expected.to_square


def check_attempt(
    fen: str, solution: Sequence[str], moves: Sequence[str], *, gave_up: bool = False
) -> AttemptCheck:
    """Проверка ходов попытки (ходы игрока и сыгранные ответы соперника по очереди).

    Ход игрока верен, если совпадает с решением; последний — ещё и любой мат. Попытка
    обрывается на первом неверном ходе игрока (`failed`); `gave_up` — игрок сдался.
    """
    if len(moves) > len(solution):
        raise AttemptError("Ходов больше, чем в решении")
    board = chess.Board(fen)
    for index, uci in enumerate(moves):
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise AttemptError(f"Некорректный ход {uci}") from exc
        expected = chess.Move.from_uci(solution[index])
        if index % 2 == 1:
            if move != expected:
                raise AttemptError("Ответ соперника не совпадает с решением")
        elif not board.is_legal(move):
            raise AttemptError(f"Нелегальный ход {uci}")
        elif not _same_move(move, expected) and not (
            index == len(solution) - 1 and gives_mate(board, move)
        ):
            return AttemptCheck("failed", expected=solution[index])
        board.push(expected if _same_move(move, expected) else move)
    if len(moves) == len(solution):
        return AttemptCheck("solved")
    if gave_up:
        return AttemptCheck("failed", expected=solution[len(moves) + len(moves) % 2])
    if len(moves) % 2 == 0:
        raise AttemptError("Попытка должна заканчиваться ходом игрока")
    return AttemptCheck("continue", reply=solution[len(moves)])
