"""Классы ходов из известных партий на настоящем Stockfish (SPEC, сессия 3).

Каждый ход анализируется отдельно: позиция до хода соперника → до хода → после,
в свежем однопоточном процессе, поэтому результат детерминирован. Глубина 16
(а не 18 по умолчанию) — ради времени; на 18 классы этих ходов те же.
"""

import asyncio
import io
from dataclasses import dataclass

import chess
import chess.pgn
import pytest

from app.engine.analyzer import Analyzer
from app.engine.pool import EnginePool
from app.review.classify import MoveClassification, classify_game
from app.review.evaluate import evaluate_game, replay
from app.review.openings import default_openings
from app.review.types import MoveClass

DEPTH = 16
PARALLEL = 4

GAMES = {
    # Морфи — герцог Брауншвейгский и граф Изуар, Париж 1858.
    "opera": "1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7 "
    "8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 "
    "14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8#",
    # Бирн — Фишер, Нью-Йорк 1956, «партия века».
    "byrne": "1. Nf3 Nf6 2. c4 g6 3. Nc3 Bg7 4. d4 O-O 5. Bf4 d5 6. Qb3 dxc4 7. Qxc4 c6 "
    "8. e4 Nbd7 9. Rd1 Nb6 10. Qc5 Bg4 11. Bg5 Na4 12. Qa3 Nxc3 13. bxc3 Nxe4 14. Bxe7 Qb6 "
    "15. Bc4 Nxc3 16. Bc5 Rfe8+ 17. Kf1 Be6",
    # Каспаров — Топалов, Вейк-ан-Зее 1999.
    "kasparov": "1. e4 d6 2. d4 Nf6 3. Nc3 g6 4. Be3 Bg7 5. Qd2 c6 6. f3 b5 7. Nge2 Nbd7 "
    "8. Bh6 Bxh6 9. Qxh6 Bb7 10. a3 e5 11. O-O-O Qe7 12. Kb1 a6 13. Nc1 O-O-O 14. Nb3 exd4 "
    "15. Rxd4 c5 16. Rd1 Nb6 17. g3 Kb8 18. Na5 Ba8 19. Bh3 d5 20. Qf4+ Ka7 21. Rhe1 d4 "
    "22. Nd5 Nbxd5 23. exd5 Qd6 24. Rxd4 cxd4 25. Re7+ Kb6 26. Qxd4+",
    # Левицкий — Маршалл, Бреслау 1912, «золотой дождь».
    "marshall": "1. d4 e6 2. e4 d5 3. Nc3 c5 4. Nf3 Nc6 5. exd5 exd5 6. Be2 Nf6 7. O-O Be7 "
    "8. Bg5 O-O 9. dxc5 Be6 10. Nd4 Bxc5 11. Nxe6 fxe6 12. Bg4 Qd6 13. Bh3 Rae8 14. Qd2 Bb4 "
    "15. Bxf6 Rxf6 16. Rad1 Qc5 17. Qe2 Bxc3 18. bxc3 Qxc3 19. Rxd5 Nd4 20. Qh5 Ref8 "
    "21. Re5 Rh6 22. Qg5 Rxh3 23. Rc5 Qg3",
    # Рети — Тартаковер, Вена 1910.
    "reti": "1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Nf6 5. Qd3 e5 6. dxe5 Qa5+ 7. Bd2 Qxe5 "
    "8. O-O-O Nxe4 9. Qd8+",
    "scholar": "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7#",
    "queen_hangs": "1. e4 e5 2. Nf3 Qh4 3. d3",
}


@dataclass(frozen=True)
class Case:
    game: str
    ply: int
    san: str
    expected: frozenset[MoveClass]
    miss: bool = False

    @property
    def id(self) -> str:
        return f"{self.game}-{self.san}"


def case(game: str, ply: int, san: str, *expected: MoveClass, miss: bool = False) -> Case:
    return Case(game, ply, san, frozenset(expected), miss)


CASES = [
    case("opera", 1, "e4", MoveClass.BOOK),
    case("opera", 7, "dxe5", MoveClass.BOOK),
    case("opera", 12, "Nf6", MoveClass.MISTAKE),
    case("opera", 13, "Qb3", MoveClass.GREAT),
    # Жертва качества: Rxd7 Rxd7 Rd1.
    case("opera", 25, "Rxd7", MoveClass.BRILLIANT),
    # Жертва ферзя с матом в 2, но белые уже выигрывают подавляюще (win% ≥ 97).
    case("opera", 31, "Qb8+", MoveClass.BEST, MoveClass.GREAT),
    case("opera", 32, "Nxb8", MoveClass.FORCED),
    case("byrne", 21, "Bg5", MoveClass.BLUNDER),
    # 17… Be6!! — ферзь b6 оставлен под боем.
    case("byrne", 34, "Be6", MoveClass.BRILLIANT),
    # Конь a5 оставлен под боем короля.
    case("kasparov", 51, "Qxd4+", MoveClass.BRILLIANT),
    # Ферзь под тремя взятиями.
    case("marshall", 46, "Qg3", MoveClass.BRILLIANT),
    # Жертва ферзя с матом: только ход, но не brilliant.
    case("reti", 17, "Qd8+", MoveClass.GREAT),
    case("scholar", 6, "Nf6", MoveClass.BLUNDER),
    case("scholar", 7, "Qxf7#", MoveClass.GREAT),
    # Соперник подставил ферзя, а белые не взяли.
    case("queen_hangs", 5, "d3", MoveClass.BLUNDER, miss=True),
]


async def classify_ply(stockfish: str, game: str, ply: int) -> tuple[str, MoveClassification]:
    pgn = chess.pgn.read_game(io.StringIO(GAMES[game]))
    assert pgn is not None
    moves = list(pgn.mainline_moves())[:ply]
    first = max(0, ply - 2)
    start = replay(pgn.board(), moves)[first]
    segment = moves[first:]
    async with EnginePool(stockfish, 1, threads=1, hash_mb=128) as pool:
        evals = await Analyzer(pool).analyse_game(
            replay(start, segment), segment, depth=DEPTH, multipv=3
        )
    result = evaluate_game(start, segment, evals)
    return result.moves[-1].san, classify_game(result.moves, default_openings())[-1]


@pytest.fixture(scope="module")
async def classified(stockfish_path: str) -> dict[str, tuple[str, MoveClassification]]:
    limit = asyncio.Semaphore(PARALLEL)

    async def run(item: Case) -> tuple[str, MoveClassification]:
        async with limit:
            return await classify_ply(stockfish_path, item.game, item.ply)

    results = await asyncio.gather(*(run(item) for item in CASES))
    return {item.id: result for item, result in zip(CASES, results, strict=True)}


@pytest.mark.parametrize("item", CASES, ids=lambda item: item.id)
def test_known_move_class(
    classified: dict[str, tuple[str, MoveClassification]], item: Case
) -> None:
    san, result = classified[item.id]
    assert san == item.san
    assert result.move_class in item.expected
    assert result.is_miss is item.miss
    if result.move_class is MoveClass.BRILLIANT:
        assert result.sacrifice is not None
