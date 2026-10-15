"""Дебюты (SPEC §4.7): база lichess-org/chess-openings (CC0) и «книжные» ходы.

Данные — `data/openings.tsv` (eco, name, pgn, uci, epd), собирается скриптом
`scripts/build_openings.py`. Позиции сравниваются по EPD, поэтому переходы
из одного порядка ходов в другой распознаются.

Книжной считается любая позиция на линиях базы, а не только конечная: у многих
промежуточных позиций нет своего названия (≈ половина), но это всё равно теория.
Название даёт только позиция, которой линия заканчивается.
"""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import chess

DATA_PATH = Path(__file__).resolve().parent / "data" / "openings.tsv"


@dataclass(frozen=True, slots=True)
class Opening:
    eco: str
    name: str
    pgn: str


class OpeningBook(Protocol):
    """Книга дебютов для классификации `book`. Сейчас — только база Lichess;
    позже сюда же встанет Polyglot (решение 2026-10-15)."""

    def is_book(self, board: chess.Board, move: chess.Move) -> bool: ...


class OpeningsDB:
    """База дебютов: названия по EPD и множество всех книжных позиций."""

    def __init__(self, rows: Sequence[tuple[Opening, Sequence[chess.Move]]]) -> None:
        self.named: dict[str, Opening] = {}
        self.positions: set[str] = set()
        for opening, moves in rows:
            board = chess.Board()
            for move in moves:
                board.push(move)
                self.positions.add(board.epd())
            # При дублях EPD (одна позиция разными порядками ходов) — первое название.
            self.named.setdefault(board.epd(), opening)

    @classmethod
    def from_tsv(cls, path: Path = DATA_PATH) -> "OpeningsDB":
        with path.open(encoding="utf-8", newline="") as fh:
            rows = [
                (
                    Opening(eco=row["eco"], name=row["name"], pgn=row["pgn"]),
                    [chess.Move.from_uci(uci) for uci in row["uci"].split()],
                )
                for row in csv.DictReader(fh, delimiter="\t")
            ]
        return cls(rows)

    def contains(self, board: chess.Board) -> bool:
        return board.epd() in self.positions

    def is_book(self, board: chess.Board, move: chess.Move) -> bool:
        board.push(move)
        try:
            return self.contains(board)
        finally:
            board.pop()

    def lookup(self, board: chess.Board) -> Opening | None:
        return self.named.get(board.epd())

    def identify(self, positions: Sequence[chess.Board]) -> Opening | None:
        """Дебют партии — самое глубокое совпадение позиции партии с базой."""
        found = None
        for board in positions:
            found = self.lookup(board) or found
        return found

    def book_plies(self, positions: Sequence[chess.Board]) -> int:
        """Сколько первых полуходов подряд ведут в книжные позиции (для фаз §4.6)."""
        plies = 0
        for board in positions[1:]:
            if not self.contains(board):
                break
            plies += 1
        return plies


@lru_cache(maxsize=1)
def default_openings() -> OpeningsDB:
    """База из `data/openings.tsv`, загружается один раз на процесс (~0.2 с)."""
    return OpeningsDB.from_tsv()
