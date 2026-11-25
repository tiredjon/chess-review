"""Каталог курсов из базы дебютов (`review/data/openings.tsv`): семейства → варианты → линии.

Имя линии в базе — «Семейство: Вариант, Подвариант, …». Семейство — часть до `:`, вариант —
до первой `,` после `:`; у имени без `:` семейство — до первой `,` (например «Polish
Opening, with d5»), а вариант совпадает с семейством (основные позиции дебюта).

Семейства — по алфавиту, варианты и линии внутри — в порядке базы (по ECO, затем по
имени). Ответ API один на процесс: JSON и его gzip считаются один раз, ETag — хеш JSON."""

import csv
import gzip
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chess
from pydantic import BaseModel

from app.review.openings import DATA_PATH, OpeningsDB, default_openings


class CatalogLine(BaseModel):
    name: str
    eco: str
    uci: list[str]
    pgn: str


class CatalogVariation(BaseModel):
    name: str
    lines: list[CatalogLine]


class CatalogFamily(BaseModel):
    name: str
    variations: list[CatalogVariation]


class Catalog(BaseModel):
    families: list[CatalogFamily]


def split_name(name: str) -> tuple[str, str]:
    """(семейство, вариант) по полному имени линии."""
    if ":" in name:
        family, rest = name.split(":", 1)
        variation = rest.split(",", 1)[0].strip()
        return family.strip(), variation or family.strip()
    family = name.split(",", 1)[0].strip()
    return family, family


def build_catalog(path: Path = DATA_PATH) -> Catalog:
    families: dict[str, dict[str, list[CatalogLine]]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            family, variation = split_name(row["name"])
            line = CatalogLine(
                name=row["name"], eco=row["eco"], uci=row["uci"].split(), pgn=row["pgn"]
            )
            families.setdefault(family, {}).setdefault(variation, []).append(line)
    return Catalog(
        families=[
            CatalogFamily(
                name=family,
                variations=[
                    CatalogVariation(name=name, lines=lines) for name, lines in variations.items()
                ],
            )
            for family, variations in sorted(families.items(), key=lambda kv: kv[0].casefold())
        ]
    )


@dataclass(frozen=True, slots=True)
class CatalogPayload:
    json: bytes
    gzip: bytes
    etag: str


@lru_cache(maxsize=1)
def catalog_payload() -> CatalogPayload:
    """Готовый ответ `GET /courses/catalog` (≈ 0,1 с на первый вызов)."""
    body = build_catalog().model_dump_json().encode()
    return CatalogPayload(
        json=body,
        gzip=gzip.compress(body, compresslevel=6, mtime=0),
        etag='"' + hashlib.sha256(body).hexdigest()[:32] + '"',
    )


def line_san(line: Sequence[chess.Move]) -> list[str]:
    board = chess.Board()
    sans: list[str] = []
    for move in line:
        sans.append(board.san(move))
        board.push(move)
    return sans


def line_pgn(line: Sequence[chess.Move]) -> str:
    """«1. e4 c5 2. Nf3» — как в базе дебютов."""
    parts: list[str] = []
    for ply, san in enumerate(line_san(line)):
        parts.append(f"{ply // 2 + 1}. {san}" if ply % 2 == 0 else san)
    return " ".join(parts)


def line_opening(
    line: Sequence[chess.Move], openings: OpeningsDB | None = None
) -> tuple[str | None, str | None]:
    """(название, ECO) самой глубокой позиции линии с названием в базе дебютов."""
    db = openings or default_openings()
    board = chess.Board()
    found = None
    for move in line:
        board.push(move)
        found = db.lookup(board) or found
    return (found.name, found.eco) if found else (None, None)
