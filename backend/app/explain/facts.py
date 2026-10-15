"""Факты для объяснений (SPEC §6.1): проверенные данные разбора → JSON для LLM и шаблонов.

Чистые функции без I/O. Источник — сохранённый разбор хода (строка `moves`: оценки,
линии и мотивы в формате `app/workers/serialize.py`); ничего не пересчитывается
движком. LLM получает только эти факты и переводит их в текст, поэтому всё, что
может появиться в объяснении (ходы, поля), должно быть здесь.

Оценки — с точки зрения игрока, сделавшего ход: «+1.20» — он лучше, «#3» — он
матует в 3 хода, «-#2» — ему мат в 2, «#» — ход поставил мат.
"""

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import chess

from app.review.material import material_balance
from app.review.types import MoveClass, Phase

# Ходы, которые объясняются (SPEC §6.1); плюс любой ход с флагом miss.
EXPLAINED = frozenset(
    {
        MoveClass.BRILLIANT,
        MoveClass.GREAT,
        MoveClass.INACCURACY,
        MoveClass.MISTAKE,
        MoveClass.BLUNDER,
    }
)
ERRORS = frozenset({MoveClass.INACCURACY, MoveClass.MISTAKE, MoveClass.BLUNDER})
# Длина линий в фактах (полуходы): дальше LLM всё равно не нужно.
LINE_PLIES = 6
# Полуходы опровержения, по которым считается потеря материала.
SWING_PLIES = 4
# Ключевые моменты партии: самые большие падения win% (не меньше порога).
KEY_MOMENTS = 3
KEY_MOMENT_MIN_DROP = 10.0


class MoveLike(Protocol):
    """Сохранённый разбор хода — строка `moves` (поля как в `app.db.models.Move`)."""

    @property
    def ply(self) -> int: ...
    @property
    def san(self) -> str: ...
    @property
    def uci(self) -> str: ...
    @property
    def fen_before(self) -> str: ...
    @property
    def eval_before_cp(self) -> int | None: ...
    @property
    def eval_after_cp(self) -> int | None: ...
    @property
    def mate_before(self) -> int | None: ...
    @property
    def mate_after(self) -> int | None: ...
    @property
    def win_before(self) -> float: ...
    @property
    def win_after(self) -> float: ...
    @property
    def move_class(self) -> MoveClass: ...
    @property
    def is_miss(self) -> bool: ...
    @property
    def best_san(self) -> str | None: ...
    @property
    def pv(self) -> list[Any] | None: ...
    @property
    def reply_pv(self) -> list[Any] | None: ...
    @property
    def motifs(self) -> dict[str, Any] | None: ...
    @property
    def phase(self) -> Phase: ...


def format_eval(cp: int | None, mate: int | None) -> str:
    if mate is not None:
        if mate == 0:
            return "#"
        return f"#{mate}" if mate > 0 else f"-#{-mate}"
    return f"{(cp or 0) / 100:+.2f}"


def _color(fen: str) -> str:
    return "white" if fen.split()[1] == "w" else "black"


def _fullmove(fen: str) -> int:
    return int(fen.split()[5])


def line_san(line: Sequence[Mapping[str, str]] | None, plies: int = LINE_PLIES) -> list[str]:
    """SAN линии; нулевой ход угрозы («любой ход соперника») — "--"."""
    return [step["san"] for step in (line or [])[:plies]]


def motif_facts(motif: Mapping[str, Any]) -> dict[str, Any]:
    """Мотив из JSON разбора → факт: фигура (без цвета), её поле, цели «Kg8»."""
    pieces: list[str] = motif.get("pieces", [])
    squares: list[str] = motif.get("squares", [])
    result: dict[str, Any] = {"type": motif["type"]}
    if pieces and squares:
        result["piece"] = pieces[0].upper()
        result["square"] = squares[0]
        targets = [f"{p.upper()}{s}" for p, s in zip(pieces[1:], squares[1:], strict=False)]
        if targets:
            result["targets"] = targets
    gain = motif.get("gain_cp")
    if gain:
        result["material_gain"] = round(gain / 100)
    line = line_san(motif.get("line"))
    if line:
        result["line_san"] = line
    if motif["type"] == "mate_in_n" and line:
        # N — число ходов матующей стороны в линии.
        result["n"] = (len(motif.get("line", [])) + 1) // 2
    return result


def material_swing(fen_before: str, uci: str, reply: Sequence[Mapping[str, str]] | None) -> int:
    """Изменение материала игрока (в пешках) после хода и первых полуходов опровержения."""
    board = chess.Board(fen_before)
    mover = board.turn
    baseline = material_balance(board, mover)
    board.push_uci(uci)
    for step in (reply or [])[:SWING_PLIES]:
        move = chess.Move.from_uci(step["uci"])
        if not move or not board.is_legal(move):
            break
        board.push(move)
    return material_balance(board, mover) - baseline


def is_explained(move: MoveLike) -> bool:
    return move.move_class in EXPLAINED or move.is_miss


def move_facts(move: MoveLike) -> dict[str, Any] | None:
    """Факты хода; None — ход не из объясняемых (книжный, лучший, хороший …)."""
    if not is_explained(move):
        return None
    motifs = move.motifs or {}
    facts: dict[str, Any] = {
        "move_number": _fullmove(move.fen_before),
        "color": _color(move.fen_before),
        "move_san": move.san,
        "class": move.move_class.value,
        "is_miss": move.is_miss,
        "eval_before": format_eval(move.eval_before_cp, move.mate_before),
        "eval_after": format_eval(move.eval_after_cp, move.mate_after),
        "win_chance_drop": round(max(0.0, move.win_before - move.win_after)),
        "phase": move.phase.value,
    }
    is_error = move.move_class in ERRORS or move.is_miss
    # «Лучше было» — только у ошибок: у brilliant / great с Δ ≤ 2 лучший ход
    # формально другой, но подсказывать его — неверно.
    if is_error and move.best_san and move.best_san != move.san:
        facts["best_move_san"] = move.best_san
        facts["best_line_san"] = line_san(move.pv)
        missed = [motif_facts(m) for m in motifs.get("missed", [])]
        if missed:
            facts["motifs_missed"] = missed
    played = [motif_facts(m) for m in motifs.get("played", [])]
    if played:
        facts["motifs_played"] = played
    if move.move_class in ERRORS:
        refutation = line_san(move.reply_pv)
        if refutation:
            facts["refutation_line_san"] = refutation
        punished = [motif_facts(m) for m in motifs.get("refutation", [])]
        if punished:
            facts["motifs_in_refutation"] = punished
        swing = material_swing(move.fen_before, move.uci, move.reply_pv)
        if swing:
            facts["material_swing"] = f"{swing:+d}"
    sacrifice = motifs.get("sacrifice")
    if move.move_class == MoveClass.BRILLIANT and sacrifice:
        facts["sacrifice"] = {
            "squares": sacrifice.get("squares", []),
            "material": sacrifice.get("material_drop"),
        }
    return facts


@dataclass(frozen=True, slots=True)
class GameInfo:
    """То, что нужно сводке из строк `games` / `analyses`."""

    white: str
    black: str
    white_elo: int | None
    black_elo: int | None
    result: str
    opening_name: str | None
    user_color: str | None
    white_accuracy: float | None
    black_accuracy: float | None
    phase_accuracy: Mapping[str, Mapping[str, float | None]] | None


def _key_moment(move: MoveLike) -> dict[str, Any]:
    moment: dict[str, Any] = {
        "move_number": _fullmove(move.fen_before),
        "color": _color(move.fen_before),
        "move_san": move.san,
        "class": move.move_class.value,
        "eval_before": format_eval(move.eval_before_cp, move.mate_before),
        "eval_after": format_eval(move.eval_after_cp, move.mate_after),
    }
    if move.best_san and move.best_san != move.san:
        moment["best_move_san"] = move.best_san
    return moment


def _typical_errors(moves: Sequence[MoveLike]) -> list[dict[str, Any]]:
    """Мотивы, на которых игрок терял: опровержения его ошибок и упущенное."""
    counts: Counter[str] = Counter()
    for move in moves:
        if move.move_class not in ERRORS and not move.is_miss:
            continue
        motifs = move.motifs or {}
        seen = {m["type"] for m in motifs.get("refutation", []) + motifs.get("missed", [])}
        counts.update(seen)
    return [{"type": kind, "count": count} for kind, count in counts.most_common(3)]


def game_facts(game: GameInfo, moves: Sequence[MoveLike]) -> dict[str, Any]:
    """Факты для общего разбора партии (SPEC §6.3)."""
    players: dict[str, Any] = {}
    for color, name, elo, accuracy in (
        ("white", game.white, game.white_elo, game.white_accuracy),
        ("black", game.black, game.black_elo, game.black_accuracy),
    ):
        own = [move for move in moves if _color(move.fen_before) == color]
        classes = Counter(move.move_class.value for move in own if move.move_class in ERRORS)
        phases = (game.phase_accuracy or {}).get(color, {})
        players[color] = {
            "name": name,
            "elo": elo,
            "accuracy": round(accuracy, 1) if accuracy is not None else None,
            "phase_accuracy": {
                phase: round(value, 1) for phase, value in phases.items() if value is not None
            },
            "errors": {kind: classes[kind] for kind in ("inaccuracy", "mistake", "blunder")},
            "misses": sum(move.is_miss for move in own),
            "typical_errors": _typical_errors(own),
        }
    # Только ошибки: падение win% у лучшего хода — артефакт глубины, а не перелом.
    drops = sorted(
        (
            move
            for move in moves
            if move.move_class in ERRORS and move.win_before - move.win_after >= KEY_MOMENT_MIN_DROP
        ),
        key=lambda move: move.win_before - move.win_after,
        reverse=True,
    )[:KEY_MOMENTS]
    return {
        "result": game.result,
        "opening": game.opening_name,
        "user_color": game.user_color,
        "moves": (len(moves) + 1) // 2,
        "players": players,
        "key_moments": [_key_moment(move) for move in sorted(drops, key=lambda m: m.ply)],
    }


def facts_hash(facts: Mapping[str, Any], *, salt: str = "") -> str:
    """Ключ кэша объяснений: факты + `salt` (версия промпта, провайдер и модель)."""
    payload = json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{salt}\n{payload}".encode()).hexdigest()


def _walk(value: Any) -> Any:
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    else:
        yield value


def grounded_tokens(facts: Mapping[str, Any]) -> frozenset[str]:
    """Все ходы, поля и обозначения фигур («Kg8»), упомянутые в фактах. Объяснение
    может ссылаться только на них (`app/explain/validate.py`)."""
    tokens: set[str] = set()
    for value in _walk(facts):
        if isinstance(value, str):
            tokens.add(value)
    return frozenset(tokens)
