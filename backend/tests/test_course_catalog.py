"""Каталог курсов из базы дебютов: семейства, варианты, линии, готовый ответ API."""

import gzip
import json

import chess

from app.courses.catalog import (
    build_catalog,
    catalog_payload,
    line_opening,
    line_pgn,
    line_san,
    split_name,
)
from app.review.openings import DATA_PATH


def test_split_name() -> None:
    assert split_name("Sicilian Defense: Najdorf Variation, English Attack") == (
        "Sicilian Defense",
        "Najdorf Variation",
    )
    assert split_name("Sicilian Defense: Najdorf Variation") == (
        "Sicilian Defense",
        "Najdorf Variation",
    )
    assert split_name("Sicilian Defense") == ("Sicilian Defense", "Sicilian Defense")
    assert split_name("Polish Opening, with d5") == ("Polish Opening", "Polish Opening")


def test_catalog_covers_every_line() -> None:
    catalog = build_catalog()
    rows = DATA_PATH.read_text(encoding="utf-8").splitlines()[1:]
    lines = [line for f in catalog.families for v in f.variations for line in v.lines]
    assert len(lines) == len(rows)
    names = [f.name for f in catalog.families]
    assert names == sorted(names, key=str.casefold)
    assert len(set(names)) == len(names)

    sicilian = next(f for f in catalog.families if f.name == "Sicilian Defense")
    najdorf = next(v for v in sicilian.variations if v.name == "Najdorf Variation")
    base = next(
        line for line in najdorf.lines if line.name == "Sicilian Defense: Najdorf Variation"
    )
    assert base.eco == "B90"
    assert base.uci == [
        "e2e4",
        "c7c5",
        "g1f3",
        "d7d6",
        "d2d4",
        "c5d4",
        "f3d4",
        "g8f6",
        "b1c3",
        "a7a6",
    ]
    assert base.pgn.startswith("1. e4 c5 2. Nf3")
    # Все линии легальны от начальной позиции.
    for line in lines:
        board = chess.Board()
        for uci in line.uci:
            board.push_uci(uci)


def test_catalog_payload() -> None:
    payload = catalog_payload()
    assert payload is catalog_payload()  # один раз на процесс
    data = json.loads(payload.json)
    assert json.loads(gzip.decompress(payload.gzip)) == data
    assert len(payload.gzip) < len(payload.json) / 4
    assert set(data["families"][0]) == {"name", "variations"}
    assert set(data["families"][0]["variations"][0]["lines"][0]) == {"name", "eco", "uci", "pgn"}
    assert payload.etag.startswith('"')
    assert payload.etag.endswith('"')


def test_line_helpers() -> None:
    line = [chess.Move.from_uci(u) for u in ["e2e4", "c7c5", "g1f3", "b8c6", "f1b5"]]
    assert line_san(line) == ["e4", "c5", "Nf3", "Nc6", "Bb5"]
    assert line_pgn(line) == "1. e4 c5 2. Nf3 Nc6 3. Bb5"
    assert line_opening(line) == ("Sicilian Defense: Nyezhmetdinov-Rossolimo Attack", "B30")
    # Линия вне базы: название — от самой глубокой позиции с названием.
    name, eco = line_opening([*line, chess.Move.from_uci("a7a5")])
    assert name == "Sicilian Defense: Nyezhmetdinov-Rossolimo Attack"
    assert eco == "B30"
    assert line_opening([chess.Move.from_uci("a2a3"), chess.Move.from_uci("h7h5")])[0] is not None
