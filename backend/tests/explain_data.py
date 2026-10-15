"""Разбор Оперной партии для тестов объяснений.

`data/opera_review.json` — строки `moves` настоящего разбора (Stockfish 19, depth 14,
формат `app/workers/serialize.py`) плюс точность. Пересобрать: прогнать
`analyse_game` по `opera_game.pgn` и сохранить `move_row` каждого хода.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.explain.facts import GameInfo
from app.review.types import MoveClass, Phase

DATA = Path(__file__).parent / "data"
REVIEW: dict[str, Any] = json.loads((DATA / "opera_review.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class MoveRow:
    """Строка `moves` без БД (поля `app.db.models.Move`)."""

    ply: int
    san: str
    uci: str
    fen_before: str
    eval_before_cp: int | None
    eval_after_cp: int | None
    mate_before: int | None
    mate_after: int | None
    win_before: float
    win_after: float
    accuracy: float
    move_class: MoveClass
    is_miss: bool
    best_uci: str | None
    best_san: str | None
    pv: list[Any] | None
    multipv: list[Any] | None
    reply_pv: list[Any] | None
    motifs: dict[str, Any] | None
    phase: Phase
    id: int = 0


def opera_moves() -> list[MoveRow]:
    return [
        MoveRow(
            **{
                **row,
                "move_class": MoveClass(row["move_class"]),
                "phase": Phase(row["phase"]),
                "id": row["ply"],
            }
        )
        for row in REVIEW["moves"]
    ]


def opera_move(san: str) -> MoveRow:
    return next(move for move in opera_moves() if move.san == san)


def opera_info(user_color: str | None = "black") -> GameInfo:
    return GameInfo(
        white="Paul Morphy",
        black="Duke Karl / Count Isouard",
        white_elo=None,
        black_elo=None,
        result="1-0",
        opening_name="Philidor Defense",
        user_color=user_color,
        white_accuracy=REVIEW["white_accuracy"],
        black_accuracy=REVIEW["black_accuracy"],
        phase_accuracy=REVIEW["phase_accuracy"],
    )
