"""Шаблонные объяснения по фактам — без LLM (SPEC §6.2).

Полноценный режим, а не заглушка: при `LLM_PROVIDER=none`, при ошибке провайдера
и когда ответ LLM не прошёл проверку SAN. Текст собирается только из фактов,
поэтому ходы в нём всегда настоящие. Падежей избегаем конструкциями
«вилка (конь e7 → король g8, ладья c8)».
"""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

Lang = Literal["ru", "en"]

CLASS_NAMES: dict[str, dict[Lang, str]] = {
    "book": {"ru": "Книжный ход", "en": "Book move"},
    "forced": {"ru": "Единственный ход", "en": "Forced move"},
    "brilliant": {"ru": "Блестящий ход", "en": "Brilliant move"},
    "great": {"ru": "Отличный ход", "en": "Great move"},
    "best": {"ru": "Лучший ход", "en": "Best move"},
    "excellent": {"ru": "Превосходный ход", "en": "Excellent move"},
    "good": {"ru": "Хороший ход", "en": "Good move"},
    "inaccuracy": {"ru": "Неточность", "en": "Inaccuracy"},
    "mistake": {"ru": "Ошибка", "en": "Mistake"},
    "blunder": {"ru": "Зевок", "en": "Blunder"},
}

# Короткие пояснения для ходов, которые не разбираются подробно.
SIMPLE_TEXT: dict[str, dict[Lang, str]] = {
    "book": {"ru": "Ход из дебютной теории.", "en": "A known opening move."},
    "forced": {"ru": "Других легальных ходов не было.", "en": "This was the only legal move."},
    "best": {"ru": "Ход совпадает с выбором движка.", "en": "The engine's top choice."},
    "excellent": {
        "ru": "Почти не уступает лучшему ходу.",
        "en": "Almost as strong as the best move.",
    },
    "good": {
        "ru": "Крепкий ход, хотя был немного сильнее.",
        "en": "A solid move, though a slightly stronger one existed.",
    },
}

MOTIF_NAMES: dict[str, dict[Lang, str]] = {
    "hanging_piece": {"ru": "незащищённая фигура", "en": "hanging piece"},
    "fork": {"ru": "вилка", "en": "fork"},
    "pin": {"ru": "связка", "en": "pin"},
    "skewer": {"ru": "линейный удар", "en": "skewer"},
    "discovered_attack": {"ru": "вскрытое нападение", "en": "discovered attack"},
    "discovered_check": {"ru": "вскрытый шах", "en": "discovered check"},
    "double_check": {"ru": "двойной шах", "en": "double check"},
    "mate_in_n": {"ru": "мат", "en": "checkmate"},
    "mate_threat": {"ru": "угроза мата", "en": "mate threat"},
    "back_rank": {"ru": "мат по последней горизонтали", "en": "back-rank mate"},
    "trapped_piece": {"ru": "пойманная фигура", "en": "trapped piece"},
    "removing_defender": {"ru": "устранение защитника", "en": "removing the defender"},
    "overload": {"ru": "перегрузка", "en": "overloaded defender"},
    "promotion": {"ru": "превращение пешки", "en": "promotion"},
    "promotion_threat": {"ru": "угроза превращения", "en": "promotion threat"},
}

PIECE_NAMES: dict[str, dict[Lang, str]] = {
    "K": {"ru": "король", "en": "king"},
    "Q": {"ru": "ферзь", "en": "queen"},
    "R": {"ru": "ладья", "en": "rook"},
    "B": {"ru": "слон", "en": "bishop"},
    "N": {"ru": "конь", "en": "knight"},
    "P": {"ru": "пешка", "en": "pawn"},
}

PHASE_NAMES: dict[str, dict[Lang, str]] = {
    "opening": {"ru": "дебют", "en": "opening"},
    "middlegame": {"ru": "миттельшпиль", "en": "middlegame"},
    "endgame": {"ru": "эндшпиль", "en": "endgame"},
}

COLOR_NAMES: dict[str, dict[Lang, str]] = {
    "white": {"ru": "белые", "en": "White"},
    "black": {"ru": "чёрные", "en": "Black"},
}


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def pawns(n: int, lang: Lang) -> str:
    if lang == "ru":
        return f"{n} {plural_ru(n, 'пешка', 'пешки', 'пешек')}"
    return f"{n} pawn" if abs(n) == 1 else f"{n} pawns"


def move_label(facts: Mapping[str, Any]) -> str:
    dots = "." if facts["color"] == "white" else "..."
    return f"{facts['move_number']}{dots} {facts['move_san']}"


def _piece(token: str, lang: Lang) -> str:
    """«Kg8» → «король g8»."""
    name = PIECE_NAMES.get(token[0], {}).get(lang)
    return f"{name} {token[1:]}" if name else token


def describe_motif(motif: Mapping[str, Any], lang: Lang) -> str:
    """«вилка (конь e7 → король g8, ладья c8)»."""
    kind = motif["type"]
    name = MOTIF_NAMES.get(kind, {}).get(lang, kind.replace("_", " "))
    if kind == "mate_in_n" and "n" in motif:
        n = motif["n"]
        if lang == "ru":
            return f"мат в {n} {plural_ru(n, 'ход', 'хода', 'ходов')}"
        return f"mate in {n}"
    details = []
    if "piece" in motif:
        actor = _piece(f"{motif['piece']}{motif['square']}", lang)
        targets = ", ".join(_piece(target, lang) for target in motif.get("targets", []))
        details.append(f"{actor} → {targets}" if targets else actor)
    gain = motif.get("material_gain")
    if gain and gain > 0:
        details.append(("+" if lang == "en" else "выигрыш ") + pawns(gain, lang))
    return f"{name} ({'; '.join(details)})" if details else name


def _first_motif(motifs: Sequence[Mapping[str, Any]] | None, lang: Lang) -> str | None:
    return describe_motif(motifs[0], lang) if motifs else None


def explain_simple(move_class: str, lang: Lang) -> str:
    """Ходы, для которых фактов не строят (книжный, лучший, хороший …)."""
    return SIMPLE_TEXT.get(move_class, {}).get(lang) or CLASS_NAMES[move_class][lang] + "."


def _headline(facts: Mapping[str, Any], lang: Lang) -> str:
    """Первое предложение: класс хода и изменение оценки."""
    kind = facts["class"]
    label = move_label(facts)
    before, after = facts["eval_before"], facts["eval_after"]
    ru = lang == "ru"
    if kind == "brilliant":
        squares = ", ".join((facts.get("sacrifice") or {}).get("squares", []))
        if ru:
            where = f" на {squares}" if squares else ""
            return (
                f"{label} — блестящая жертва{where}: материал отдаётся, "
                f"но оценка держится ({after})."
            )
        where = f" on {squares}" if squares else ""
        return (
            f"{label} is a brilliant sacrifice{where}: material is given up, "
            f"yet the evaluation holds ({after})."
        )
    if kind == "great":
        if ru:
            return f"{label} — сильнейший ход: остальные заметно хуже ({before} → {after})."
        return f"{label} is the key move: the alternatives are clearly worse ({before} → {after})."
    if kind in ("inaccuracy", "mistake", "blunder"):
        name = CLASS_NAMES[kind][lang]
        evaluation = "оценка" if ru else "evaluation"
        return f"{name}: {label}, {evaluation} {before} → {after}."
    return f"{label}: {before} → {after}."


def explain_move(facts: Mapping[str, Any], lang: Lang) -> str:
    """Объяснение хода по фактам `move_facts`."""
    kind = facts["class"]
    ru = lang == "ru"
    sentences = [_headline(facts, lang)]

    if facts.get("is_miss"):
        sentences.append(
            "Соперник только что ошибся, но шанс наказать его упущен."
            if ru
            else "The opponent had just erred, but the chance to punish it was missed."
        )

    played = _first_motif(facts.get("motifs_played"), lang)
    if played and kind in ("brilliant", "great"):
        sentences.append(f"Мотив: {played}." if ru else f"Motif: {played}.")

    refutation = facts.get("refutation_line_san") or []
    if refutation:
        punished = _first_motif(facts.get("motifs_in_refutation"), lang)
        reply = refutation[0]
        if ru:
            text = f"Соперник отвечает {reply}"
            text += f" — {punished}" if punished else ""
        else:
            text = f"The opponent replies {reply}"
            text += f" — {punished}" if punished else ""
        swing = facts.get("material_swing")
        if swing and swing.startswith("-"):
            loss = pawns(int(swing[1:]), lang)
            text += f", потеря материала: {loss}" if ru else f", losing {loss}"
        sentences.append(text + ".")

    best = facts.get("best_move_san")
    if best:
        missed = _first_motif(facts.get("motifs_missed"), lang)
        text = f"Лучше было {best}" if ru else f"Better was {best}"
        text += f" — {missed}" if missed else ""
        sentences.append(text + ".")
    return " ".join(sentences)


def _player(players: Mapping[str, Any], color: str, lang: Lang) -> str:
    player = players[color]
    return f"{player['name']} ({COLOR_NAMES[color][lang]})"


def summarize_game(facts: Mapping[str, Any], lang: Lang) -> str:
    """Общий разбор партии: 3–5 пунктов по фактам `game_facts`."""
    ru = lang == "ru"
    players = facts["players"]
    points: list[str] = []

    accuracy = [
        f"{_player(players, color, lang)} — {players[color]['accuracy']}%"
        for color in ("white", "black")
        if players[color]["accuracy"] is not None
    ]
    if accuracy:
        points.append(("Точность: " if ru else "Accuracy: ") + ", ".join(accuracy) + ".")

    for color in ("white", "black"):
        errors = players[color]["errors"]
        if not any(errors.values()):
            continue
        parts = [
            f"{CLASS_NAMES[kind][lang].lower()}: {count}" for kind, count in errors.items() if count
        ]
        points.append(f"{_player(players, color, lang)}: {', '.join(parts)}.")

    for moment in facts["key_moments"][:2]:
        label = move_label(moment)
        name = CLASS_NAMES[moment["class"]][lang]
        text = (
            f"Перелом: {label} ({name.lower()}), {moment['eval_before']} → {moment['eval_after']}"
            if ru
            else f"Turning point: {label} ({name.lower()}), "
            f"{moment['eval_before']} → {moment['eval_after']}"
        )
        if "best_move_san" in moment:
            text += (
                f"; лучше было {moment['best_move_san']}"
                if ru
                else f"; better was {moment['best_move_san']}"
            )
        points.append(text + ".")

    focus = [facts["user_color"]] if facts.get("user_color") else ["white", "black"]
    for color in focus:
        typical = players[color]["typical_errors"]
        if typical:
            names = ", ".join(
                MOTIF_NAMES.get(item["type"], {}).get(lang, item["type"]) for item in typical
            )
            points.append(
                f"{_player(players, color, lang)}: чаще всего наказывали — {names}."
                if ru
                else f"{_player(players, color, lang)} was most often punished by: {names}."
            )
        phases = players[color]["phase_accuracy"]
        if len(phases) > 1:
            weakest = min(phases, key=lambda phase: phases[phase])
            phase = PHASE_NAMES.get(weakest, {}).get(lang, weakest)
            points.append(
                f"{_player(players, color, lang)}: слабее всего — {phase} ({phases[weakest]}%)."
                if ru
                else f"{_player(players, color, lang)}: weakest phase — {phase} "
                f"({phases[weakest]}%)."
            )
    if not points:
        points.append("Партия без явных ошибок." if ru else "A clean game without clear errors.")
    return "\n".join(f"- {point}" for point in points[:5])
