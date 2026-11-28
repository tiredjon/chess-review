"""Партии мастеров из книг (`app/books/`): описательная нотация, разметка текста книги,
готовый `data/master_games.pgn`."""

import io

import chess
import chess.pgn
import pytest

from app.books.build import OUTPUT, build, render
from app.books.descriptive import NotationError, Tracker, looks_like_move
from app.books.extract import RawGame, capablanca_games, convert, lasker_games


def _play(*moves: str) -> list[str]:
    tracker = Tracker()
    sans = []
    for text in moves:
        move = tracker.parse(text).move
        sans.append(tracker.board.san(move))
        tracker.push(move)
    return sans


def test_descriptive_basic() -> None:
    assert _play("P - K 4", "P - Q B 4", "Kt - K B 3", "P - Q 3", "P-Q4", "PxP", "KtxP") == [
        "e4",
        "c5",
        "Nf3",
        "d6",
        "d4",
        "cxd4",
        "Nxd4",
    ]


def test_descriptive_sides_are_relative() -> None:
    """«Kt-QB3» у чёрных — c6; «B-Kt5» без фланга решается легальностью."""
    assert _play("P-K4", "P-K4", "Kt-KB3", "Kt-QB3", "B-Kt5", "P-QR3", "B-R4") == [
        "e4",
        "e5",
        "Nf3",
        "Nc6",
        "Bb5",
        "a6",
        "Ba4",
    ]


def test_descriptive_piece_identity() -> None:
    """«QKt» — конь, начавший на b1, даже если оба коня идут на одно поле."""
    tracker = Tracker()
    for text in ("P-Q4", "P-Q4", "Kt-KB3", "Kt-KB3", "P-K3", "P-K3"):
        tracker.push(tracker.parse(text).move)
    assert tracker.board.san(tracker.parse("QKt-Q2").move) == "Nbd2"
    assert tracker.board.san(tracker.parse("KKt-Q2").move) == "Nfd2"


def test_descriptive_castles_checks_and_marks() -> None:
    tracker = Tracker()
    for text in ("P-K4", "P-K4", "Kt-KB3", "Kt-QB3", "B-B4", "B-B4"):
        tracker.push(tracker.parse(text).move)
    parsed = tracker.parse("Castles!")
    assert tracker.board.is_castling(parsed.move)
    assert parsed.nag == 1
    tracker.push(parsed.move)
    tracker.push(tracker.parse("Kt-B3").move)
    # «BxPch» — из двух взятий пешки слоном только f7 с шахом.
    assert tracker.board.san(tracker.parse("BxPch").move) == "Bxf7+"


def test_descriptive_old_spellings() -> None:
    """«K-R sq» — первая горизонталь, «KT» и «I» — опечатки распознавания, «P K 4»."""
    assert _play("P K 4", "P-K4", "Kt-KB3", "Kt-QB3", "B-B4", "B-B4", "K-B sq") == [
        "e4",
        "e5",
        "Nf3",
        "Nc6",
        "Bc4",
        "Bc5",
        "Kf1",
    ]
    assert _play("P-K4", "P-K4", "KT-KB3")[-1] == "Nf3"


def test_descriptive_errors() -> None:
    tracker = Tracker()
    with pytest.raises(NotationError, match="нет легального"):
        tracker.parse("Q-R5")
    with pytest.raises(NotationError, match="не разобран"):
        tracker.parse("Zz-9")
    for text in ("P-K4", "P-K4"):
        tracker.push(tracker.parse(text).move)
    with pytest.raises(NotationError, match="неоднозначно"):
        tracker.parse("Kt-B3")  # c3 или f3
    assert tracker.board.san(tracker.parse("=Nf3").move) == "Nf3"
    assert looks_like_move("Q R - Kt 1")
    assert not looks_like_move("Diag. 100")


LASKER_SNIPPET = """
ILLUSTRATIVE GAMES FROM MASTER TOURNAMENTS

     1. Teacher-Student (Somewhere, 1910)

CHAPTER I

ILLUSTRATIVE GAMES FROM MASTER TOURNAMENTS

                GAME No. 1

    White: Teacher.   Black: Student.

   Scholar's Mate (compare p. 1).

          1. P-K4         P-K4
          2. B-B4         B-B4

Black copies White's moves.

          3. Q-R5

        ---------------------------------------
     8 | #R | #Kt| #B | #Q | #K |    | #Kt| #R |
     7 | #P | #P | #P | #P |    | #P | #P | #P |
     6 |    |    |    |    |    |    |    |    |
     5 |    |    | #B |    | #P |    |    | ^Q |
     4 |    |    | ^B |    | ^P |    |    |    |
     3 |    |    |    |    |    |    |    |    |
     2 | ^P | ^P | ^P | ^P |    | ^P | ^P | ^P |
     1 | ^R | ^Kt| ^B |    | ^K |    | ^Kt| ^R |
        ---------------------------------------

          3. ...          Kt-QB3
          4. QxBP         Mate

TABLE OF OPENINGS
"""


def test_lasker_snippet() -> None:
    (raw,) = lasker_games(LASKER_SNIPPET)
    assert (raw.white, raw.black, raw.event, raw.year) == (
        "Teacher",
        "Student",
        "Somewhere",
        "1910",
    )
    assert raw.opening == "Scholar's Mate"
    converted = convert(raw)
    assert converted.error is None
    game = converted.game
    assert game.board().variation_san(list(game.mainline_moves())) == (
        "1. e4 e5 2. Bc4 Bc5 3. Qh5 Nc6 4. Qxf7#"
    )
    assert game.headers["Result"] == "1-0"
    assert game.next() is not None
    second_black = list(game.mainline())[3]
    assert second_black.comment == "Black copies White's moves."


CAPABLANCA_SNIPPET = """
PART II

GAME 1. QUEEN'S GAMBIT DECLINED

(Match, 1909)

White: A. Player. Black: B. Player.

        1. P - Q 4                P - Q 4
        2. P - Q B 4              P - K 3

The classical reply. {160}

        3. Kt - Q B 3             Kt - K B 3
             Resigns.

*** END OF THE PROJECT GUTENBERG EBOOK
"""


def test_capablanca_snippet() -> None:
    (raw,) = capablanca_games(CAPABLANCA_SNIPPET)
    assert (raw.white, raw.black, raw.event, raw.year) == (
        "A. Player",
        "B. Player",
        "Match",
        "1909",
    )
    assert raw.opening == "Queen's Gambit Declined"
    converted = convert(raw)
    assert converted.error is None
    assert converted.plies == 6
    assert converted.game.headers["Result"] == "0-1"  # сдались белые, их ход
    assert list(converted.game.mainline())[3].comment == "The classical reply."


def test_convert_reports_bad_record() -> None:
    raw = RawGame("lasker", "1", "W", "B", None, None, None, ["     1. P-K5    P-K4"])
    converted = convert(raw)
    assert converted.error is not None
    assert converted.game.headers["Result"] == "*"


def _games() -> list[chess.pgn.Game]:
    stream = io.StringIO(OUTPUT.read_text(encoding="utf-8"))
    games = []
    while (game := chess.pgn.read_game(stream)) is not None:
        games.append(game)
    return games


def test_master_games_file() -> None:
    games = _games()
    assert len(games) == 60
    keys = [g.headers["BookGame"] for g in games]
    assert len(set(keys)) == len(keys)
    for game in games:
        assert not game.errors, game.headers["BookGame"]
        assert game.headers["Result"] in {"1-0", "0-1", "1/2-1/2"}, game.headers["BookGame"]
        assert game.headers["Annotator"] in {"Edward Lasker", "J. R. Capablanca"}
        assert "public domain" in game.headers["Source"]
        assert game.board().fen() == chess.STARTING_FEN
        moves = list(game.mainline())
        assert len(moves) >= 20, game.headers["BookGame"]
        assert any(node.comment for node in moves), game.headers["BookGame"]


@pytest.mark.parametrize(
    ("key", "line"),
    [
        (
            "lasker-35",  # Рети — Тартаковер, Вена 1910
            "1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Nf6 5. Qd3 e5 6. dxe5 Qa5+ 7. Bd2 Qxe5 "
            "8. O-O-O Nxe4 9. Qd8+ Kxd8 10. Bg5+ Kc7 11. Bd8#",
        ),
        (
            "lasker-39",  # Ротлеви — Рубинштейн, Лодзь 1907
            "1. d4 d5 2. Nf3 e6 3. e3 c5 4. c4 Nc6 5. Nc3 Nf6 6. dxc5 Bxc5 7. a3 a6 8. b4 Bd6 "
            "9. Bb2 O-O 10. Qd2 Qe7 11. Bd3 dxc4 12. Bxc4 b5 13. Bd3 Rd8 14. Qe2 Bb7 15. O-O "
            "Ne5 16. Nxe5 Bxe5 17. f4 Bc7 18. e4 Rac8 19. e5 Bb6+ 20. Kh1 Ng4 21. Be4 Qh4 "
            "22. g3 Rxc3 23. gxh4 Rd2 24. Qxd2 Bxe4+ 25. Qg2 Rh3",
        ),
    ],
)
def test_famous_games(key: str, line: str) -> None:
    game = next(g for g in _games() if g.headers["BookGame"] == key)
    assert game.board().variation_san(list(game.mainline_moves())) == line


def test_build_checks_diagrams() -> None:
    converted, problems = build(LASKER_SNIPPET, CAPABLANCA_SNIPPET)
    assert problems == []
    text = render(converted)
    assert text.count("[Event ") == 2
    assert '[Annotator "Edward Lasker"]' in text
    assert '[BookGame "capablanca-1"]' in text
    # Диаграмма с ошибкой — сборка сообщает о ней.
    broken = LASKER_SNIPPET.replace("|    |    | ^Q |", "| ^Q |    |    |")
    _, problems = build(broken, CAPABLANCA_SNIPPET)
    assert problems == ["lasker 1: диаграмма после полухода 5"]
