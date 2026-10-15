"""Оркестрация разбора партии (SPEC §3): оценки позиций → точность, классы, мотивы, дебют.

`review_game` — чистая функция над готовыми оценками позиций. `analyse_game` добавляет
к ней движок: оценки берёт у инъецированного анализатора (`app.engine.analyzer.Analyzer`),
а сам разбор — CPU-работа на ~1 с — уводит в поток, чтобы не стопорить event loop
(другие партии в воркере в это время ждут ответов движка).
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import chess

from app.review.classify import MoveClassification, classify_game
from app.review.evaluate import MoveEval, evaluate_game, replay
from app.review.motifs.context import MoveMotifs, game_motifs
from app.review.openings import Opening, OpeningsDB, default_openings
from app.review.types import Phase, PositionEval

ProgressCallback = Callable[[int, int], None]


class GameAnalyser(Protocol):
    """Оценки всех позиций партии; `positions` на одну длиннее `moves`."""

    async def analyse_game(
        self,
        positions: Sequence[chess.Board],
        moves: Sequence[chess.Move],
        *,
        depth: int,
        multipv: int,
        on_progress: ProgressCallback | None = None,
    ) -> list[PositionEval]: ...


@dataclass(frozen=True, slots=True)
class MoveReview:
    eval: MoveEval
    classification: MoveClassification
    motifs: MoveMotifs


@dataclass(frozen=True, slots=True)
class GameReview:
    moves: list[MoveReview]
    accuracy: dict[chess.Color, float | None]
    phase_accuracy: dict[chess.Color, dict[Phase, float | None]]
    opening: Opening | None


def review_game(
    start: chess.Board,
    moves: Sequence[chess.Move],
    evals: Sequence[PositionEval],
    *,
    openings: OpeningsDB | None = None,
) -> GameReview:
    """Разбор партии по оценкам позиций (`evals[i]` — после i полуходов).

    `openings` — база дебютов; по умолчанию встроенная база Lichess.
    """
    book = openings if openings is not None else default_openings()
    positions = replay(start, moves)
    game = evaluate_game(start, moves, evals, book_plies=book.book_plies(positions))
    classes = classify_game(game.moves, book)
    motifs = game_motifs(game.moves)
    return GameReview(
        moves=[
            MoveReview(eval=move, classification=classification, motifs=move_motifs)
            for move, classification, move_motifs in zip(game.moves, classes, motifs, strict=True)
        ],
        accuracy=game.accuracy,
        phase_accuracy=game.phase_accuracy,
        opening=book.identify(positions),
    )


async def analyse_game(
    analyser: GameAnalyser,
    start: chess.Board,
    moves: Sequence[chess.Move],
    *,
    depth: int,
    multipv: int,
    openings: OpeningsDB | None = None,
    on_progress: ProgressCallback | None = None,
) -> GameReview:
    """Полный разбор: оценки движка (`on_progress(done, total)` по позициям) + `review_game`."""
    positions = replay(start, moves)
    evals = await analyser.analyse_game(
        positions, moves, depth=depth, multipv=multipv, on_progress=on_progress
    )
    return await asyncio.to_thread(review_game, start, moves, evals, openings=openings)
