"""Каталог типовых эндшпилей. Чистые данные, без I/O.

Правила каталога (проверяет `tests/test_endgame_catalog.py`):
- позиция легальна, в ней ≤ 7 фигур (вместе с королями) — цель проверяется таблицами Syzygy;
- ученик всегда играет стороной, которая ходит в `fen`;
- `goal` совпадает с ответом таблиц для ходящего (`win` — выигрыш, `draw` — ничья); ответы
  зафиксированы в `tests/data/endgame_tablebase.json` (сверено с tablebase.lichess.ovh,
  пересборка — `python -m app.endgames fixtures`).

Названия и подсказки — на фронте (словарь `endgames.positions[id]`), здесь только шахматы.
Порядок — порядок показа: внутри категории от простого к сложному.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import chess

Goal = Literal["win", "draw"]


class Category(StrEnum):
    PAWN = "pawn"
    ROOK = "rook"
    QUEEN = "queen"
    MATE = "mate"


@dataclass(frozen=True, slots=True)
class CatalogPosition:
    id: str
    category: Category
    fen: str
    goal: Goal
    # 1 — азы, 2 — нужна техника, 3 — трудно.
    difficulty: int

    @property
    def color(self) -> chess.Color:
        """Цвет ученика — сторона на ходу."""
        return chess.Board(self.fen).turn


CATALOG: tuple[CatalogPosition, ...] = (
    # --- Пешечные ---
    # Король впереди пешки на 5-й: Ke6 / Kd6 / Kf6 — занять поле перед пешкой через одно.
    CatalogPosition(
        "pawn_opposition_win", Category.PAWN, "4k3/8/8/4K3/4P3/8/8/8 w - - 0 1", "win", 1
    ),
    # Единственный ход Ke5 — оппозиция, белый король не пройдёт на ключевые поля.
    CatalogPosition(
        "pawn_opposition_draw", Category.PAWN, "8/8/4k3/8/8/4K3/4P3/8 b - - 0 1", "draw", 1
    ),
    # Король на ключевом поле (c4 / d4 / e4 для пешки d2) — выигрыш при любой очереди хода.
    CatalogPosition("pawn_key_squares", Category.PAWN, "8/8/3k4/8/3K4/8/3P4/8 w - - 0 1", "win", 2),
    # Правило квадрата: Ke4 / Ke5 — войти в квадрат пешки a4.
    CatalogPosition("pawn_square", Category.PAWN, "8/8/8/8/P4k2/8/8/K7 b - - 0 1", "draw", 1),
    # Отдалённая проходная a-пешка отвлекает короля, белый король съедает пешки на фланге.
    CatalogPosition(
        "pawn_outside_passer", Category.PAWN, "8/7p/6p1/4k3/P7/4K1P1/8/8 w - - 0 1", "win", 2
    ),
    CatalogPosition(
        "pawn_outside_passer_2", Category.PAWN, "8/6pp/8/4k3/P7/4K1P1/7P/8 w - - 0 1", "win", 3
    ),
    # --- Ладейные ---
    # Лусена: отрезать короля шахом (Rd1+) и построить «мост» (Rd4).
    CatalogPosition("rook_lucena", Category.ROOK, "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1", "win", 2),
    CatalogPosition(
        "rook_lucena_2", Category.ROOK, "2K5/2P1k3/8/8/8/8/1r6/3R4 w - - 0 1", "win", 3
    ),
    # Филидор: ладья на 6-й горизонтали (Ra6), пока пешка не пошла вперёд.
    CatalogPosition("rook_philidor", Category.ROOK, "3k4/8/8/3PK3/8/8/r7/7R b - - 0 1", "draw", 2),
    # Пешка пошла на 6-ю — шахи сзади: единственный ход Re1+.
    CatalogPosition(
        "rook_philidor_checks", Category.ROOK, "3k4/8/3PK3/8/8/8/7R/r7 b - - 0 1", "draw", 2
    ),
    # Ванкура: ладья сбоку (на f-вертикали) держит пешку a6 под боем.
    CatalogPosition("rook_vancura", Category.ROOK, "R7/6k1/P7/8/8/8/5r2/1K6 b - - 0 1", "draw", 3),
    # Ладья против пешки: король идёт к пешке, ладья держит поле превращения.
    CatalogPosition("rook_vs_pawn_win", Category.ROOK, "8/8/8/8/8/2k5/2p5/K6R w - - 0 1", "win", 2),
    # Ладья против пешки, защита: король рядом с пешкой — ладья отдаётся за неё.
    CatalogPosition(
        "rook_vs_pawn_draw", Category.ROOK, "7K/8/8/8/2k5/8/2p5/7R b - - 0 1", "draw", 2
    ),
    # --- Ферзь против пешки на 7-й ---
    # Центральная пешка: шахами заставить короля встать перед пешкой, подтянуть короля.
    CatalogPosition("queen_vs_pawn", Category.QUEEN, "7K/8/8/8/8/8/3pk3/7Q w - - 0 1", "win", 2),
    # Крайняя пешка обычно ничья, но король рядом: Kb3! — мат раньше пата.
    CatalogPosition(
        "queen_vs_rook_pawn", Category.QUEEN, "7Q/8/8/8/2K5/8/p7/1k6 w - - 0 1", "win", 2
    ),
    # Слоновая пешка: защита — уйти в угол (Kc1 / Kd1), взятие пешки даёт пат.
    CatalogPosition(
        "queen_vs_bishop_pawn", Category.QUEEN, "8/8/K7/8/8/8/2pk3Q/8 b - - 0 1", "draw", 2
    ),
    # --- Элементарные маты ---
    CatalogPosition("mate_queen", Category.MATE, "8/8/8/4k3/8/8/8/1Q2K3 w - - 0 1", "win", 1),
    CatalogPosition("mate_two_rooks", Category.MATE, "8/8/3k4/8/8/8/8/R3K2R w - - 0 1", "win", 1),
    CatalogPosition("mate_rook", Category.MATE, "8/8/8/4k3/8/8/8/R3K3 w - - 0 1", "win", 1),
    CatalogPosition(
        "mate_two_bishops", Category.MATE, "8/8/8/4k3/8/8/8/2B1KB2 w - - 0 1", "win", 2
    ),
    CatalogPosition(
        "mate_bishop_knight", Category.MATE, "8/8/8/4k3/8/8/8/1N2KB2 w - - 0 1", "win", 3
    ),
)

_BY_ID = {position.id: position for position in CATALOG}


def catalog_position(position_id: str) -> CatalogPosition | None:
    return _BY_ID.get(position_id)
