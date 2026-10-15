"""Проверка ответа LLM (SPEC §6.2): каждый ход в тексте должен быть из фактов.

Ход в тексте — токен английского SAN (`Nf3`, `exd5`, `O-O`, `e8=Q+`). Голое поле
(`e4`) — это и ход пешкой, и просто поле; оно допустимо, если поле встречается
в фактах (в ходах, полях мотивов, целях «Kg8»). Обозначение фигуры с полем
(`Kg8`) допустимо как ход или как цель мотива из фактов. Русская нотация
(`Кf3`, `Фd1`) запрещена: ходы — только в английском SAN.
"""

import re
from collections.abc import Iterable

_SQUARE_RE = re.compile(r"[a-h][1-8]")
# Граница слова и для кириллицы: \w в Python — юникодный.
_SAN_RE = re.compile(
    r"(?<![\w-])("
    r"[O0]-[O0](?:-[O0])?"
    r"|[KQRBN][a-h]?[1-8]?x?[a-h][1-8]"
    r"|[a-h]x[a-h][1-8](?:=[QRBN])?"
    r"|[a-h][1-8](?:=[QRBN])?"
    r")[+#]?(?![\w-])"
)
_RUSSIAN_SAN_RE = re.compile(r"(?<![\w-])(?:Кр|[КФЛС])[a-h]?[1-8]?[x:]?[a-h][1-8](?!\w)")


def normalize(san: str) -> str:
    """SAN без шаха / мата и с буквенной рокировкой."""
    return san.rstrip("+#!?").replace("0", "O")


def mentioned_moves(text: str) -> list[str]:
    return [match.group(0) for match in _SAN_RE.finditer(text)]


def invalid_moves(text: str, grounded: Iterable[str]) -> list[str]:
    """Ходы из текста, которых нет в фактах (пусто — текст прошёл проверку)."""
    allowed = {normalize(token) for token in grounded}
    squares = {square for token in allowed for square in _SQUARE_RE.findall(token)}
    problems: list[str] = []
    for token in mentioned_moves(text):
        move = normalize(token)
        if move in allowed:
            continue
        if _SQUARE_RE.fullmatch(move) and move in squares:
            continue
        problems.append(token)
    problems.extend(match.group(0) for match in _RUSSIAN_SAN_RE.finditer(text))
    return list(dict.fromkeys(problems))
