"""Промпты объяснений (SPEC §6.2–6.3). Меняя текст, увеличь PROMPT_VERSION —
он входит в ключ кэша, и старые объяснения перестанут подставляться."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.explain.templates import Lang

PROMPT_VERSION = "1"

LANG_NAMES: dict[Lang, str] = {"ru": "русский", "en": "English"}

_RULES = (
    "Объясняй только на основе фактов. Не придумывай ходы, варианты и оценки — "
    "упоминай только ходы и поля, которые есть в фактах. Ходы пиши в английском SAN "
    "(Nf3, exd5, O-O) на любом языке ответа. Оценки в фактах — с точки зрения игрока, "
    "сделавшего ход: «+1.20» — он лучше на 1.2 пешки, «#3» — он матует в 3 хода, "
    "«-#2» — ему мат в 2. Уровень — клубный игрок. Без markdown."
)

MOVE_SYSTEM = "Ты шахматный тренер. {rules} 2–4 предложения. Язык ответа: {lang}."
SUMMARY_SYSTEM = (
    "Ты шахматный тренер. {rules} Подведи итог партии: 3–5 пунктов, каждый с новой "
    "строки и начинается с «- ». Если user_color задан — пиши для этого игрока. "
    "Язык ответа: {lang}."
)


def move_system(lang: Lang) -> str:
    return MOVE_SYSTEM.format(rules=_RULES, lang=LANG_NAMES[lang])


def summary_system(lang: Lang) -> str:
    return SUMMARY_SYSTEM.format(rules=_RULES, lang=LANG_NAMES[lang])


def _facts_json(facts: Mapping[str, Any]) -> str:
    return json.dumps(facts, ensure_ascii=False, indent=1)


def move_user(facts: Mapping[str, Any]) -> str:
    return f"Факты о ходе:\n{_facts_json(facts)}\n\nОбъясни этот ход."


def summary_user(facts: Mapping[str, Any]) -> str:
    return f"Факты о партии:\n{_facts_json(facts)}\n\nПодведи итог партии."


def retry_note(invalid: Sequence[str]) -> str:
    """Добавка к запросу после ответа с ходами не из фактов."""
    return (
        f"\n\nВ прошлом ответе были ходы, которых нет в фактах: {', '.join(invalid)}. "
        "Перепиши ответ, используя только ходы и поля из фактов."
    )
