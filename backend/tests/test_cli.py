import io
from pathlib import Path

import pytest

from app.cli import main, read_game

DATA = Path(__file__).parent / "data"


def test_cli_prints_move_table(stockfish_path: str) -> None:
    out = io.StringIO()

    main(
        [
            "analyze",
            str(DATA / "opera_game.pgn"),
            "--depth",
            "8",
            "--pool",
            "2",
            "--engine",
            stockfish_path,
            "-q",
        ],
        out=out,
    )

    text = out.getvalue()
    assert "Paul Morphy" in text
    assert "Дебют: C41 Philidor Defense" in text
    # Классы: начало партии — книжное, 16… Nxb8 — единственный ход.
    assert "книга" in text.split("1. e4")[1].split("\n")[0]
    assert "вынужд." in text.split("16... Nxb8")[1].split("\n")[0]
    # Мотивы: мат по последней горизонтали.
    assert "mate_in_n, back_rank" in text.split("17. Rd8#")[1].split("\n")[0]
    assert "1. e4" in text
    assert "16... Nxb8" in text
    assert "17. Rd8#" in text
    # После мата оценка — «#».
    assert text.split("17. Rd8#")[1].split()[0] == "#"
    assert "Белые" in text
    assert "Чёрные" in text
    assert "глубина 8" in text


def test_read_game_errors(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="нет партии с номером 2"):
        read_game(DATA / "opera_game.pgn", 1)

    broken = tmp_path / "broken.pgn"
    broken.write_text("1. e4 e5 2. Ke3 Nf6 *\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Ошибка в PGN"):
        read_game(broken, 0)
