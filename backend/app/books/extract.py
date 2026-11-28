"""Партии из текстов книг Project Gutenberg → PGN с комментариями авторов.

Книги (общественное достояние в США):
- Эд. Ласкер, «Chess Strategy» (1915, перевод 1917), Gutenberg #5614 — часть II,
  «Illustrative games from master tournaments»;
- Х. Р. Капабланка, «Chess Fundamentals» (1921), Gutenberg #33870 — часть II, партии
  автора.

Ходы в книгах — колонками с отступом («1. P - K 4    P - K 4», «8. ...   Castles!»),
комментарии — абзацы без отступа между ходами. Комментарий привязывается к последнему
сыгранному ходу (до первого хода — к партии). Диаграммы, «[Illustration]» и номера
страниц «{123}» выбрасываются; варианты внутри комментариев остаются текстом.
"""

import io
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

import chess
import chess.pgn

from app.books.descriptive import NotationError, Tracker, looks_like_move

_NUMBERED = re.compile(r"^(\d+)\s*\.\s*(.*)$")
_PLACEHOLDER = re.compile(r"^\.{2,}$")
_PAGE = re.compile(r"\{\d+\}")
_FOOTNOTE = re.compile(r"\[\d+\]")
_RESIGNS = re.compile(r"^(?:and\s+)?(?:(?:white|black)\s+)?resigns?\.?$", re.IGNORECASE)
_DRAWN = re.compile(r"^(?:drawn|draw)\.?$", re.IGNORECASE)
_WINS = re.compile(r"^(?:and\s+)?wins\.?$", re.IGNORECASE)
_MATE = re.compile(r"^mate\.?$", re.IGNORECASE)  # «21. B-R6   Mate» — в колонке чёрных


@dataclass(slots=True)
class RawGame:
    source: str
    number: str
    white: str
    black: str
    event: str | None
    year: str | None
    opening: str | None
    lines: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Converted:
    raw: RawGame
    game: chess.pgn.Game
    plies: int
    error: str | None


# --- Разметка книг ----------------------------------------------------------------------


def _between(text: str, start: str, end: str, occurrence: int = 1) -> str:
    index = -1
    for _ in range(occurrence):
        index = text.index(start, index + 1)
    stop = text.find(end, index)
    return text[index : stop if stop != -1 else len(text)]


def _event(text: str) -> tuple[str | None, str | None]:
    """«(Carlsbad, 1911)» / «(Match, 1909)» → («Carlsbad», «1911»)."""
    match = re.search(r"\(([^()]*?),?\s*((?:1[89]\d\d)(?:-\d+)?)\)", text)
    if match is None:
        return None, None
    return match.group(1).strip(" ,") or None, match.group(2)[:4]


def _opening(text: str | None) -> str | None:
    """«Ruy Lopez (see p. 37).» → «Ruy Lopez»; «Queen'S» (после title()) → «Queen's»."""
    if not text:
        return None
    text = re.sub(r"\s*\((?:see|compare)[^)]*\)", "", text).strip(" .").replace("’", "'")
    text = text.replace(" declined", " Declined")
    return re.sub(r"'S\b", "'s", text) or None


def lasker_games(text: str) -> list[RawGame]:
    text = text.replace("\r", "")
    toc = _between(text, "ILLUSTRATIVE GAMES FROM MASTER TOURNAMENTS", "CHAPTER I")
    events = {}
    for match in re.finditer(r"^\s*(\d+[ab]?)\.\s+(.+)$", toc, re.MULTILINE):
        events[match.group(1)] = _event(match.group(2))
    body = _between(text, "ILLUSTRATIVE GAMES FROM MASTER TOURNAMENTS", "TABLE OF OPENINGS", 2)
    parts = re.split(r"^\s*GAME NO\.\s*(\d+)\.?\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
    games = []
    for number, chunk in zip(parts[1::2], parts[2::2], strict=True):
        lines = chunk.split("\n")
        # Обычно «White: X.   Black: Y.»; у партии 18 — просто «Emanuel Lasker.   Capablanca.»
        players = next(i for i, line in enumerate(lines) if line.strip())
        # У партии 27 дебют на той же строке: «Black: Tarrasch.   French Defence».
        names = re.search(
            r"White:\s*(.+?)\.?\s+Black:\s*(.+?)\.?(?:\s{2,}.*)?$", lines[players]
        ) or re.search(r"^\s*(.+?)\.?\s{2,}(.+?)\.?\s*$", lines[players])
        assert names is not None, lines[players]
        opening_at = next((i for i in range(players + 1, len(lines)) if lines[i].strip()), players)
        opening = lines[opening_at].strip() if opening_at > players else None
        if opening is not None and _tokens(lines[opening_at]) is not None:
            opening, opening_at = None, players  # сразу ходы — дебют не назван
        event, year = events.get(number.rstrip("."), (None, None))
        year = YEARS.get(("lasker", number), year)
        games.append(
            RawGame(
                source="lasker",
                number=number.rstrip("."),
                white=names.group(1).strip(),
                black=names.group(2).strip(),
                event=event,
                year=year,
                opening=_opening(opening),
                lines=lines[opening_at + 1 :],
            )
        )
    return games


def capablanca_games(text: str) -> list[RawGame]:
    text = text.replace("\r", "")
    start = text.index("\nPART II\n")
    stop = text.find("*** END OF", start)
    body = text[start:stop]
    parts = re.split(r"^GAME (\d+)\.\s*(.+)$", body, flags=re.MULTILINE)
    games = []
    for number, opening, chunk in zip(parts[1::3], parts[2::3], parts[3::3], strict=True):
        lines = chunk.split("\n")
        players = next(i for i, line in enumerate(lines) if line.startswith("White:"))
        header = " ".join(lines[:players])
        match = re.search(r"White:\s*(.+?)\.?\s+Black:\s*(.+?)\.?\s*$", lines[players])
        assert match is not None, lines[players]
        event, year = _event(header)
        games.append(
            RawGame(
                source="capablanca",
                number=number,
                white=match.group(1).strip(),
                black=match.group(2).strip(),
                event=event,
                year=year,
                opening=_opening(opening.title()),
                lines=lines[players + 1 :],
            )
        )
    return games


# --- Ходы и комментарии -----------------------------------------------------------------


def _is_noise(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or "|" in stripped
        or stripped.startswith(("---", "A    B", "Diag", "[Illustration", "*"))
        or bool(re.fullmatch(r"\{\d+\}", stripped))
    )


def _is_result(token: str) -> bool:
    return any(r.match(token) for r in (_RESIGNS, _DRAWN, _WINS, _MATE))


def _tokens(line: str) -> tuple[int | None, list[str]] | None:
    """Строка ходов с отступом → (номер или None, ходы). Не ходы — None."""
    line = _PAGE.sub("", line).replace("/*", "").replace("*/", "")
    if not line[:1].isspace() or _is_noise(line):
        return None
    stripped = line.strip()
    number = None
    if match := _NUMBERED.match(stripped):
        # «7.. ...» — лишняя точка у номера
        number, stripped = int(match.group(1)), re.sub(r"^\.\s*(?=\.)", "", match.group(2))
    tokens = []
    for token in (t.strip() for t in re.split(r"\s{2,}|\t", stripped)):
        if token and not looks_like_move(token):
            # «K - Kt 1 P - Kt 5» — два хода через один пробел
            parts = re.split(r"(?<=[1-8!?]) (?=[KQRBPO])", token)
            if len(parts) == 2 and all(looks_like_move(part) for part in parts):
                tokens += parts
                continue
        if token:
            tokens.append(token)
    if not tokens:
        return (number, []) if number is not None else None
    if not all(_PLACEHOLDER.match(t) or looks_like_move(t) or _is_result(t) for t in tokens):
        return None
    return number, tokens


_Item = tuple[str, str | tuple[int | None, list[str]]]


def _paragraphs(lines: list[str]) -> Iterator[_Item]:
    """Поток («moves», (номер, ходы)) и («comment», текст)."""
    buffer: list[str] = []

    def flush() -> Iterator[_Item]:
        text = " ".join(" ".join(buffer).split())
        text = re.sub(r"(?<=\w)- (?=\w)", "-", text)  # перенос строки внутри «Q-R5ch»
        text = _FOOTNOTE.sub("", _PAGE.sub("", text)).strip()
        buffer.clear()
        if text:
            yield "comment", text

    for line in lines:
        parsed = _tokens(line)
        if parsed is not None:
            yield from flush()
            yield "moves", parsed
        elif _is_noise(line):
            if not line.strip():
                buffer.append("")
            continue
        else:
            buffer.append(line.strip())
    yield from flush()


_DIAGRAM_ROW = re.compile(r"^\s*([1-8])\s*\|(.*)\|\s*$")
_DIAGRAM_PIECES = {"P": "p", "Kt": "n", "B": "b", "R": "r", "Q": "q", "K": "k"}


def diagrams(raw: RawGame) -> list[tuple[int, str]]:
    """Диаграммы партии у Ласкера: (полуходов сыграно до диаграммы, расстановка FEN).
    Строка диаграммы — «8 | #R |    | #B | …», «#» — чёрная фигура, «^» — белая."""
    result = []
    plies = 0
    rows: dict[int, str] = {}
    for line in raw.lines:
        if row := _DIAGRAM_ROW.match(line):
            cells = [c.strip() for c in row.group(2).split("|")]
            if len(cells) != 8:
                continue
            fen_row = ""
            for cell in cells:
                if not cell:
                    fen_row += "1"
                    continue
                letter = _DIAGRAM_PIECES[cell[1:]]
                fen_row += letter if cell[0] == "#" else letter.upper()
            rows[int(row.group(1))] = fen_row
            if len(rows) == 8:
                placement = "/".join(rows[r] for r in range(8, 0, -1))
                placement = re.sub(r"1+", lambda m: str(len(m.group(0))), placement)
                result.append((plies, chess.Board(f"{placement} w - - 0 1").board_fen()))
                rows = {}
            continue
        parsed = _tokens(line)
        if parsed is not None:
            plies += sum(1 for t in parsed[1] if not _PLACEHOLDER.match(t) and not _is_result(t))
    return result


def _result_token(token: str, board: chess.Board) -> str | None:
    if _RESIGNS.match(token):
        return "0-1" if board.turn == chess.WHITE else "1-0"
    if _DRAWN.match(token):
        return "1/2-1/2"
    if _MATE.match(token):
        return "1-0" if board.turn == chess.BLACK else "0-1"  # матовал сделавший ход
    if _WINS.match(token):
        return "1-0" if board.turn == chess.BLACK else "0-1"
    return None


@dataclass(slots=True)
class _Step:
    token: str
    comment: str = ""


@dataclass(slots=True)
class _Script:
    """Запись партии: ходы по порядку, комментарий после каждого, итог."""

    steps: list[_Step]
    intro: str = ""
    result_token: str | None = None
    outro: str = ""
    error: str | None = None


def _outro_result(text: str, board: chess.Board) -> str | None:
    """Итог из текста после последнего хода: «Black resigned», «… and mate at R7»."""
    if match := re.search(r"\b(White|Black)\s+resign", text):
        return "0-1" if match.group(1) == "White" else "1-0"
    if re.match(r"(?:and|followed by)\b[^.]*\bmate\b", text, re.IGNORECASE):
        return "1-0" if board.turn == chess.BLACK else "0-1"  # матует сделавший ход
    return None


def _script(raw: RawGame, start_ply: int = 0) -> _Script:
    """Ходы из строк книги с проверкой номеров: номер N — ход белых N (полуход 2N−2),
    «N. ...» — ход чёрных N. Строка без номера продолжает запись."""
    fixes = FIXES.get((raw.source, raw.number), {})
    script = _Script(steps=[])

    def comment(text: str) -> None:
        if script.result_token is not None:
            script.outro = f"{script.outro} {text}".strip()
        elif script.steps:
            script.steps[-1].comment = f"{script.steps[-1].comment} {text}".strip()
        else:
            script.intro = f"{script.intro} {text}".strip()

    for kind, value in _paragraphs(raw.lines):
        if kind == "comment":
            assert isinstance(value, str)
            comment(value)
            continue
        if script.result_token is not None or script.error:
            continue
        assert not isinstance(value, str)
        number, tokens = value[0], list(value[1])
        ply = start_ply + len(script.steps)
        if number is not None:
            black = bool(tokens) and bool(_PLACEHOLDER.match(tokens[0]))
            expected = 2 * (number - 1) + int(black)
            if tokens == [] and ply == expected + 1:
                continue  # «15.» без хода — повтор номера перед ходом чёрных
            # Опечатка в номере на один ход допустима: легальность ходов всё равно проверится.
            if abs(expected - ply) not in (0, 2):
                script.error = f"номер хода {number}, ожидался полуход {ply + 1}"
                continue
        for token in tokens:
            if _PLACEHOLDER.match(token):
                continue
            if _is_result(token):
                script.result_token = token
                break
            script.steps.append(_Step(fixes.get((len(script.steps) + start_ply, token), token)))
    return script


def _depth(tracker: Tracker, steps: list[_Step], limit: int) -> int:
    """Сколько следующих ходов записи разбирается (неоднозначные — любым вариантом)."""
    if limit == 0 or not steps:
        return 0
    try:
        moves, _ = tracker.candidates(steps[0].token)
    except NotationError:
        return 0
    best = 0
    for move in moves:
        child = tracker.copy()
        child.push(move)
        best = max(best, 1 + _depth(child, steps[1:], limit - 1))
        if best == limit:
            break
    return best


LOOKAHEAD = 8


def _choose(tracker: Tracker, steps: list[_Step], index: int) -> chess.Move:
    moves, _ = tracker.candidates(steps[index].token)
    if len(moves) <= 1:
        return tracker.parse(steps[index].token).move  # ошибка «нет хода» — отсюда
    scored = []
    for move in moves:
        child = tracker.copy()
        child.push(move)
        scored.append((_depth(child, steps[index + 1 :], LOOKAHEAD), move))
    top = max(score for score, _ in scored)
    best = [move for score, move in scored if score == top]
    if len(best) > 1:
        sans = ", ".join(tracker.board.san(m) for m in best)
        raise NotationError(f"неоднозначно {steps[index].token!r}: {sans} в {tracker.board.fen()}")
    return best[0]


def convert_all(raws: list[RawGame]) -> list[Converted]:
    """Все партии по порядку: партии с `PREFIXES` начинаются ходами уже разобранной."""
    done: dict[tuple[str, str], Converted] = {}
    for raw in raws:
        key = (raw.source, raw.number)
        prefix = None
        if key in PREFIXES:
            number, plies = PREFIXES[key]
            prefix = (done[(raw.source, number)].game, plies)
        done[key] = convert(raw, prefix)
    return list(done.values())


def convert(raw: RawGame, prefix: tuple[chess.pgn.Game, int] | None = None) -> Converted:
    """Партия книги → PGN; на первой непонятной записи останавливается с `error`.

    Неоднозначная запись («Q-B5», когда легальны и c5, и f5) решается следующими ходами:
    остаётся вариант, после которого запись партии разбирается дальше всего."""
    game = chess.pgn.Game()
    game.headers["Event"] = raw.event or "?"
    game.headers["Site"] = "?"
    game.headers["Date"] = f"{raw.year}.??.??" if raw.year else "????.??.??"
    game.headers["Round"] = "?"
    game.headers["White"] = raw.white
    game.headers["Black"] = raw.black
    if raw.opening:
        game.headers["Opening"] = raw.opening
    tracker = Tracker()
    node: chess.pgn.GameNode = game
    if prefix is not None:
        source, plies_from = prefix
        for move in source.mainline_moves():
            if len(tracker.board.move_stack) == plies_from:
                break
            node = node.add_variation(move)
            tracker.push(move)
    script = _script(raw, start_ply=len(tracker.board.move_stack))
    game.comment = script.intro
    error = script.error
    plies = 0
    for index, step in enumerate(script.steps):
        try:
            move = _choose(tracker, script.steps, index)
        except NotationError as exc:
            error = str(exc)
            break
        _, nag = tracker.candidates(step.token)
        node = node.add_variation(move)
        if nag:
            node.nags.add(nag)
        node.comment = step.comment
        tracker.push(move)
        plies += 1
    board = tracker.board
    result = None
    if error is None:
        if script.result_token is not None:
            result = _result_token(script.result_token, board)
        elif board.is_checkmate():
            result = "0-1" if board.turn == chess.WHITE else "1-0"
        last = script.steps[-1].comment if script.steps else ""
        result = result or _outro_result(script.outro or last, board)
        if script.outro:
            node.comment = f"{node.comment} {script.outro}".strip()
    game.headers["Result"] = result or "*"
    return Converted(raw=raw, game=game, plies=plies, error=error)


# Исправления опечаток книги: (книга, партия) → {(полуход от 0, запись): верная запись}.
# «=SAN» — ход алгебраически, если описательная запись неоднозначна и следующие ходы её
# не решают (выбор проверен по позиции: другой ход зевает или противоречит комментарию).
FIXES: dict[tuple[str, str], dict[tuple[int, str], str]] = {
    ("lasker", "14"): {(9, "Kt-P"): "KtxP"},
    ("lasker", "18"): {(6, "BxKtQ"): "BxKt"},
    ("lasker", "22"): {(29, "P-Kt2"): "P-Kt5"},
    ("lasker", "34"): {(46, "KR-Kt"): "KR-Kt1"},
    # 7. … Qxe5 8. O-O-O!! — знаменитая партия; …Qxa2 к ней не ведёт.
    ("lasker", "35"): {(13, "QxP"): "=Qxe5"},
    # Ладья d7 бьёт ладью d8: «38. R-Q8ch RxR 39. RxRch».
    ("lasker", "38"): {(74, "R-Q8ch"): "RxRch"},
    # Qxe6 ставит ферзя под fxe6; берётся пешка e4.
    ("capablanca", "6"): {(26, "Q x P"): "=Qxe4"},
    # g3 гонит коня f4: следующий ход чёрных — «Kt - K 3».
    ("capablanca", "7"): {(60, "P - Kt 3"): "=g3"},
}
# Партия начинается ходами другой («Move 1-8 as in Game No. 12»): (партия, полуходов).
PREFIXES: dict[tuple[str, str], tuple[str, int]] = {
    ("lasker", "13"): ("12", 16),
    ("lasker", "17"): ("16", 11),
}
# Опечатки года в оглавлении («Breslau, 1012»).
YEARS: dict[tuple[str, str], str] = {("lasker", "33"): "1912"}


def to_pgn(game: chess.pgn.Game) -> str:
    out = io.StringIO()
    exporter = chess.pgn.FileExporter(out)
    game.accept(exporter)
    return out.getvalue()
