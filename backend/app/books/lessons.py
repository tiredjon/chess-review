"""Статьи тренера по книгам Ласкера и Капабланки: позиции из партий книг.

Статья — урок тренера с видом `book` (`app/coach/lessons.py`): пересказ на RU и EN — на фронте
(`web/src/lib/coach-lessons/`), здесь — позиции к статье. Позиция — момент партии из
`data/master_games.pgn` (ключ партии `BookGame` и полуход), с комментарием автора к этому ходу;
на фронте её можно открыть и пролистать всю партию. Ссылки на статьи — из уроков фаз и навыков
(`RELATED`), из идей курса (`IDEA_LESSONS` на фронте) и через `PHASE`.
"""

import io
from dataclasses import dataclass
from functools import lru_cache

import chess
import chess.pgn

from app.books.courses import BOOK_TITLES, BookGame, book_games
from app.courses.types import ModelGame
from app.review.types import Phase

# Статья → (партия книги, полуход после хода). Порядок — порядок показа.
POSITIONS: dict[str, tuple[tuple[str, int], ...]] = {
    "book_attack_targets": (
        ("lasker-48", 25),  # Блэкберн — Нимцович: отсталая пешка d3 после c3
        ("lasker-10", 38),  # Тейхман — любители: конь на d6
        ("capablanca-6", 36),  # Хайес — Капабланка: конь d5, которого не прогнать
        ("lasker-2", 60),  # Леонхардт — Маршалл: отсталая пешка g3 теряется
    ),
    "book_king_pawns": (
        ("lasker-4", 35),  # Тарраш — Капабланка: g3 ослабляет f3 и h3
        ("lasker-30", 14),  # Тарраш — Шпильман: план Qc8 и Bh3, размен слонов
        ("lasker-42", 32),  # Капабланка — Алехин: слабость h6 уводит коня
        ("lasker-26", 21),  # Капабланка — Бланко: чёрные вынуждены ослабиться
    ),
    "book_open_files": (
        ("lasker-9", 42),  # Сальве — Маршалл: две открытые линии у чёрных
        ("lasker-47", 24),  # Тартаковер — Асталош: линию надо удержать
        ("lasker-42", 36),  # Капабланка — Алехин: ладья на седьмой
        ("lasker-5", 61),  # Гриффит — Ганстон: все линии у белых
    ),
    "book_pawn_weaknesses": (
        ("lasker-23", 10),  # Йейтс — Эссер: сдвоенные пешки за двух слонов
        ("lasker-25", 10),  # Эм. Ласкер — Тарраш: сдвоенная, но не изолированная
        ("capablanca-5", 7),  # Эм. Ласкер — Капабланка: размен на c6
        ("capablanca-14", 46),  # Маршалл — Капабланка: сдвоенная пешка давит
    ),
    "book_initiative": (
        ("lasker-33", 11),  # Бараш — Мизес: инициатива у чёрных
        ("capablanca-10", 26),  # Капабланка — Маршалл: пешка за инициативу
        ("capablanca-6", 48),  # Хайес — Капабланка: инициатива слишком рано
        ("capablanca-14", 47),  # Маршалл — Капабланка: белые не выдерживают давления
    ),
    "book_cut_off_pieces": (
        ("lasker-27", 28),  # Нимцович — Тарраш: ладья вне игры
        ("lasker-7", 29),  # Маршалл — Тарраш: слон h6 вне игры
        ("lasker-43", 44),  # Капабланка — Бернштейн: лишняя ладья вне игры
        ("lasker-47", 29),  # Тартаковер — Асталош: фигуры отрезаны от королевского фланга
    ),
    "book_endgame_king": (
        ("capablanca-5", 14),  # Эм. Ласкер — Капабланка: король на слабом фланге
        ("lasker-17", 52),  # Берлин — Рига: размен ладей при проходных
        ("lasker-2", 50),  # Леонхардт — Маршалл: король идёт вперёд
        ("capablanca-3", 72),  # Яновский — Капабланка: две проходные
    ),
    "book_rook_endings": (
        ("lasker-40", 48),  # Рубинштейн — Капабланка: активность ладьи и короля
        ("lasker-40", 60),  # там же: проходная на фланге с лишней пешкой
        ("capablanca-5", 56),  # Эм. Ласкер — Капабланка: бездействующий король
        ("capablanca-14", 48),  # Маршалл — Капабланка: активность важнее пешек
    ),
}

BOOK_LESSONS: tuple[str, ...] = tuple(POSITIONS)

# Фаза статьи — для своих примеров и тренировки (как у уроков фаз).
PHASE: dict[str, Phase] = {
    **dict.fromkeys(BOOK_LESSONS, Phase.MIDDLEGAME),
    "book_endgame_king": Phase.ENDGAME,
    "book_rook_endings": Phase.ENDGAME,
}

# Урок фазы или навыка → статьи по книгам («Теория из книг» на странице урока).
RELATED: dict[str, tuple[str, ...]] = {
    "middlegame_plans": (
        "book_attack_targets",
        "book_open_files",
        "book_king_pawns",
        "book_pawn_weaknesses",
        "book_cut_off_pieces",
        "book_initiative",
    ),
    "endgame_technique": ("book_endgame_king", "book_rook_endings"),
    "converting_advantage": ("book_endgame_king", "book_initiative"),
    "defense": ("book_king_pawns",),
}


@dataclass(frozen=True, slots=True)
class BookPosition:
    """Момент партии книги: позиция после хода `san` (полуход `ply`) и комментарий автора."""

    game: ModelGame
    ply: int
    san: str
    fen: str
    comment: str


def _model_game(game: BookGame) -> ModelGame:
    return ModelGame(
        id=f"book:{game.key}",
        node_id=0,
        white=game.white,
        black=game.black,
        year=game.year,
        result=game.result,
        pgn=game.pgn,
        source="book",
        annotator=game.annotator,
        book=BOOK_TITLES.get(game.annotator),
    )


@lru_cache(maxsize=1)
def _all_positions() -> dict[str, tuple[BookPosition, ...]]:
    games = {game.key: game for game in book_games()}
    result: dict[str, tuple[BookPosition, ...]] = {}
    for lesson, refs in POSITIONS.items():
        items = []
        for key, ply in refs:
            game = games[key]
            node: chess.pgn.GameNode = chess.pgn.read_game(io.StringIO(game.pgn))  # type: ignore[assignment]
            for _ in range(ply):
                node = node.next()  # type: ignore[assignment]
            assert isinstance(node, chess.pgn.ChildNode)
            items.append(
                BookPosition(
                    game=_model_game(game),
                    ply=ply,
                    san=node.san(),
                    fen=node.board().fen(),
                    comment=node.comment.strip(),
                )
            )
        result[lesson] = tuple(items)
    return result


def book_positions(lesson: str) -> tuple[BookPosition, ...]:
    """Позиции статьи (у остальных уроков — пусто)."""
    return _all_positions().get(lesson, ())
