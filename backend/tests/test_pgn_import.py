"""Разбор PGN для импорта: заголовки, хеш нормализованной записи, ошибки."""

from datetime import UTC, datetime
from pathlib import Path

import chess.pgn
import pytest

from app.db.models import Color
from app.importers.pgn import (
    PgnError,
    parse_game,
    parse_pgn,
    pgn_hash,
    played_at,
    read_games,
)
from app.importers.store import user_color
from app.importers.types import ImportedGame

DATA = Path(__file__).parent / "data"
OPERA = (DATA / "opera_game.pgn").read_text(encoding="utf-8")

LICHESS = """[Event "Rated Blitz game"]
[Site "https://lichess.org/abcdEFGH"]
[Date "2024.03.09"]
[White "Alice"]
[Black "bob"]
[Result "0-1"]
[UTCDate "2024.03.10"]
[UTCTime "21:05:07"]
[WhiteElo "1850"]
[BlackElo "?"]
[TimeControl "180+2"]

1. e4 { [%clk 0:03:00] } 1... e5 { [%clk 0:03:00] } 2. Qh5 (2. Nf3 Nc6) 2... Nc6 3. Bc4 Nf6 \
4. Qxf7# 0-1
"""


def _with_date(**tags: str) -> chess.pgn.Game:
    game = chess.pgn.Game()
    for name, value in tags.items():
        game.headers[name] = value
    return game


def test_parses_headers_and_opening() -> None:
    (game,) = parse_pgn(OPERA)

    assert game.white == "Paul Morphy"
    assert game.black == "Duke Karl / Count Isouard"
    assert game.result == "1-0"
    assert (game.white_elo, game.black_elo, game.time_control) == (None, None, None)
    # Неполная дата не годится для сортировки.
    assert game.played_at is None
    # Дебют — по своей базе, а не по заголовку ECO.
    assert (game.opening_eco, game.opening_name) == ("C41", "Philidor Defense")
    assert len(game.external_id) == 64
    assert game.user_color is None


def test_lichess_style_headers() -> None:
    (game,) = parse_pgn(LICHESS)

    assert (game.white_elo, game.black_elo) == (1850, None)
    assert game.time_control == "180+2"
    # UTCDate/UTCTime важнее Date.
    assert game.played_at == datetime(2024, 3, 10, 21, 5, 7, tzinfo=UTC)


def test_stored_pgn_keeps_comments_but_drops_variations() -> None:
    (game,) = parse_pgn(LICHESS)

    assert "[%clk 0:03:00]" in game.pgn
    assert "Nf3" not in game.pgn
    assert '[Site "https://lichess.org/abcdEFGH"]' in game.pgn
    # Сохранённый PGN читается обратно той же партией.
    assert pgn_hash(parse_game(game.pgn)) == game.external_id


def test_hash_ignores_formatting_comments_and_variations() -> None:
    plain = (
        '[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0'
    )
    noisy = (
        '[White "A"]\n[Black "B"]\n[Result "1-0"]\n[ECO "C20"]\n[Annotator "me"]\n\n'
        "1.e4 {king pawn} e5\n2.Qh5!? (2. Nf3) Nc6 3.Bc4 Nf6?? $4\n4.Qxf7# 1-0"
    )
    other_moves = '[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n1. d4 d5 1-0'
    other_players = plain.replace('"A"', '"C"')

    assert parse_pgn(plain)[0].external_id == parse_pgn(noisy)[0].external_id
    assert parse_pgn(plain)[0].external_id != parse_pgn(other_moves)[0].external_id
    assert parse_pgn(plain)[0].external_id != parse_pgn(other_players)[0].external_id


def test_reads_several_games_and_bom() -> None:
    games = parse_pgn("﻿" + OPERA + "\n\n" + LICHESS)

    assert [g.white for g in games] == ["Paul Morphy", "Alice"]


def test_from_position_is_supported() -> None:
    pgn = (
        '[SetUp "1"]\n[FEN "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"]\n[Result "1-0"]\n\n1. Rd8# 1-0'
    )

    (game,) = parse_pgn(pgn)

    assert game.opening_eco is None
    assert parse_game(game.pgn).board().fen() == "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "нет партий"),
        ("   \n\n", "нет партий"),
        ("hello world", "Партия 1: в партии нет ходов"),
        ("1. e4 e5 2. Ke3 *", "Партия 1: illegal san"),
        (OPERA + "\n\n1. e4 e5 2. Ke3 *", "Партия 2: illegal san"),
        (
            '[Variant "Chess960"]\n'
            '[FEN "bbqnnrkr/pppppppp/8/8/8/8/PPPPPPPP/BBQNNRKR w HFhf - 0 1"]\n\n1. e4 *',
            "только классические шахматы",
        ),
        ('[Variant "Atomic"]\n\n1. e4 *', "только классические шахматы"),
    ],
)
def test_rejects_bad_pgn(text: str, message: str) -> None:
    with pytest.raises(PgnError, match=message):
        parse_pgn(text)


def test_limits_number_of_games() -> None:
    with pytest.raises(PgnError, match="максимум 2"):
        read_games("\n\n".join([OPERA] * 3), max_games=2)


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"Date": "2020.01.02"}, datetime(2020, 1, 2, tzinfo=UTC)),
        ({"Date": "2020.01.02", "Time": "10:11:12"}, datetime(2020, 1, 2, 10, 11, 12, tzinfo=UTC)),
        ({"Date": "2020.01.02", "Time": "bad"}, datetime(2020, 1, 2, tzinfo=UTC)),
        ({"Date": "2020.??.??"}, None),
        ({"Date": "2020.02.30"}, None),
        ({"UTCDate": "2020.02.30", "Date": "2020.02.03"}, datetime(2020, 2, 3, tzinfo=UTC)),
        ({}, None),
    ],
)
def test_played_at(tags: dict[str, str], expected: datetime | None) -> None:
    assert played_at(_with_date(**tags)) == expected


def test_unknown_result_becomes_asterisk() -> None:
    (game,) = parse_pgn('[Result "2-0"]\n\n1. e4 e5 *')

    assert game.result == "*"


def _imported(white: str, black: str) -> ImportedGame:
    return ImportedGame(
        external_id="x",
        pgn="",
        white=white,
        black=black,
        white_elo=None,
        black_elo=None,
        result="*",
        time_control=None,
        played_at=None,
        opening_eco=None,
        opening_name=None,
    )


def test_user_color_by_usernames() -> None:
    assert user_color(_imported("Alice", "Bob"), ["alice", None]) == Color.WHITE
    assert user_color(_imported("Alice", "Bob"), [None, "BOB"]) == Color.BLACK
    assert user_color(_imported("Alice", "Bob"), [None, None]) is None
    # Сам с собой — цвет не определить.
    assert user_color(_imported("Alice", "alice"), ["Alice"]) is None
