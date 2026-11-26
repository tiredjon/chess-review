"""Время на ход по часам из PGN (`[%clk H:MM:SS(.s)]`, Lichess и Chess.com).

Единица — сотые доли секунды (cs): так хранит Lichess, Chess.com даёт десятые.

`%clk` — остаток на часах игрока сразу после его хода, уже с добавкой. Поэтому время на
ход = остаток перед ходом + добавка − остаток после; перед первым ходом стороны на часах
база. Отрицательное (часы подкрутили, сбой записи) считается нулём.

Считается только для контроля «база+добавка» (`180+2`, `600`): у переписки (`1/86400`) и
неизвестного контроля база неизвестна, а пороги ниже — доли базы.

Пороги (`TimeFlags`):
— цейтнот: перед ходом на часах меньше TROUBLE_SHARE базы (3+0 — < 18 с, 10+0 — < 1 мин);
— быстрый ход: потрачено не больше FAST_SHARE базы, но не меньше FAST_MIN_CS
  (3+0 — ≤ 3.6 с, 10+0 — ≤ 12 с) — у ошибки вне цейтнота это «поспешно»;
— долгое раздумье: потрачено не меньше LONG_SHARE базы (3+0 — ≥ 18 с).
"""

import re
from dataclasses import dataclass

import chess.pgn

TROUBLE_SHARE = 0.10
FAST_SHARE = 0.02
FAST_MIN_CS = 100
LONG_SHARE = 0.10

_TIME_CONTROL_RE = re.compile(r"^(\d+)(?:\+(\d+))?$")


@dataclass(frozen=True, slots=True)
class TimeControl:
    base_cs: int
    increment_cs: int


@dataclass(frozen=True, slots=True)
class GameClock:
    """Часы партии по полуходам: `clocks[i]` — остаток после полухода i + 1, `spent[i]` —
    потрачено на него; None — у хода нет `%clk`."""

    control: TimeControl
    clocks: list[int | None]
    spent: list[int | None]


@dataclass(frozen=True, slots=True)
class TimeFlags:
    trouble: bool
    fast: bool
    long: bool


def parse_time_control(value: str | None) -> TimeControl | None:
    match = _TIME_CONTROL_RE.match((value or "").strip())
    if match is None or int(match[1]) <= 0:
        return None
    return TimeControl(base_cs=int(match[1]) * 100, increment_cs=int(match[2] or 0) * 100)


def pgn_clocks(game: chess.pgn.Game) -> list[int | None]:
    """Остатки `%clk` по полуходам главной линии (None — у хода нет часов)."""
    result: list[int | None] = []
    for node in game.mainline():
        seconds = node.clock()
        result.append(None if seconds is None else max(0, round(seconds * 100)))
    return result


def move_times(clocks: list[int | None], control: TimeControl) -> list[int | None]:
    """Потрачено на каждый полуход (см. модуль). Нет остатка до или после — None."""
    spent: list[int | None] = []
    for index, after in enumerate(clocks):
        before = control.base_cs if index < 2 else clocks[index - 2]
        if after is None or before is None:
            spent.append(None)
        else:
            spent.append(max(0, before + control.increment_cs - after))
    return spent


def game_clock(game: chess.pgn.Game, time_control: str | None) -> GameClock | None:
    """Часы партии; None — контроль без базы или в PGN нет ни одного `%clk`."""
    control = parse_time_control(time_control)
    if control is None:
        return None
    clocks = pgn_clocks(game)
    if all(value is None for value in clocks):
        return None
    return GameClock(control=control, clocks=clocks, spent=move_times(clocks, control))


def clock_before(clocks: list[int | None], control: TimeControl, ply: int) -> int | None:
    """Остаток на часах ходящего перед полуходом `ply` (с 1)."""
    return control.base_cs if ply <= 2 else clocks[ply - 3]


def time_flags(before: int | None, spent: int | None, control: TimeControl) -> TimeFlags:
    base = control.base_cs
    return TimeFlags(
        trouble=before is not None and before < TROUBLE_SHARE * base,
        fast=spent is not None and spent <= max(FAST_MIN_CS, FAST_SHARE * base),
        long=spent is not None and spent >= LONG_SHARE * base,
    )
