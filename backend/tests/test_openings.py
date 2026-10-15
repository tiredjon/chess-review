import csv
from pathlib import Path

import chess
import chess.pgn
import pytest

from app.review.evaluate import replay
from app.review.openings import DATA_PATH, Opening, OpeningBook, OpeningsDB, default_openings

DATA = Path(__file__).parent / "data"


def board_after(sans: str) -> chess.Board:
    board = chess.Board()
    for san in sans.split():
        board.push_san(san)
    return board


def opera_positions() -> list[chess.Board]:
    with (DATA / "opera_game.pgn").open(encoding="utf-8") as fh:
        game = chess.pgn.read_game(fh)
    assert game is not None
    return replay(game.board(), list(game.mainline_moves()))


@pytest.fixture(scope="module")
def db() -> OpeningsDB:
    return default_openings()


def test_data_file_is_consistent() -> None:
    """epd в файле — позиция после uci, а uci — те же ходы, что в pgn."""
    with DATA_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    assert len(rows) > 3000
    for row in rows:
        board = chess.Board()
        sans = []
        for uci in row["uci"].split():
            move = chess.Move.from_uci(uci)
            sans.append(board.san(move))
            board.push(move)
        assert board.epd() == row["epd"], row
        assert [t for t in row["pgn"].split() if not t[0].isdigit()] == sans, row


def test_default_openings_is_cached_book(db: OpeningsDB) -> None:
    book: OpeningBook = db
    assert default_openings() is book
    assert len(db.named) > 3000
    assert len(db.positions) > len(db.named)


def test_lookup_and_unnamed_book_positions(db: OpeningsDB) -> None:
    ruy = db.lookup(board_after("e4 e5 Nf3 Nc6 Bb5"))
    assert ruy is not None
    assert (ruy.eco, ruy.name) == ("C60", "Ruy Lopez")

    # Промежуточная позиция линии: без названия, но книжная.
    middle = board_after("e4 e5 Nf3 Nc6 Bb5 a6 Ba4")
    assert db.lookup(middle) is None
    assert db.contains(middle)


def test_is_book(db: OpeningsDB) -> None:
    board = board_after("e4 e5")
    assert db.is_book(board, board.parse_san("Nf3"))
    assert db.is_book(board, board.parse_san("Ke2"))  # Bongcloud тоже в базе
    assert not db.is_book(board, board.parse_san("Ba6"))
    # Доска не меняется.
    assert board == board_after("e4 e5")


def test_transpositions_are_recognized(db: OpeningsDB) -> None:
    one = db.lookup(board_after("d4 Nf6 c4 e6 Nc3 Bb4"))
    other = db.lookup(board_after("c4 e6 Nc3 Nf6 d4 Bb4"))
    assert one is not None
    assert one == other
    assert one.eco == "E20"


def test_identify_deepest_match(db: OpeningsDB) -> None:
    # Книга идёт до 4. dxe5, но последняя позиция с названием — после 3. d4.
    opening = db.identify(opera_positions())
    assert opening == Opening(eco="C41", name="Philidor Defense", pgn="1. e4 e5 2. Nf3 d6 3. d4")
    assert db.identify([chess.Board()]) is None


def test_book_plies(db: OpeningsDB) -> None:
    # 1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 — книга, 4… Bxf3 — уже нет.
    assert db.book_plies(opera_positions()) == 7
    assert db.book_plies([chess.Board()]) == 0


def test_custom_db() -> None:
    line = [chess.Move.from_uci(u) for u in ("e2e4", "e7e5")]
    first = Opening(eco="X00", name="First", pgn="1. e4 e5")
    db = OpeningsDB([(first, line), (Opening(eco="X01", name="Dup", pgn="1. e4 e5"), line)])

    assert db.lookup(board_after("e4 e5")) == first
    assert db.contains(board_after("e4"))
    assert not db.contains(chess.Board())
