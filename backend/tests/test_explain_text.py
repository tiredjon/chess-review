"""Проверка SAN в ответе LLM и шаблонные объяснения."""

from typing import Any

import pytest

from app.explain import templates
from app.explain.facts import game_facts, grounded_tokens, move_facts
from app.explain.validate import invalid_moves, mentioned_moves, normalize
from tests.explain_data import opera_info, opera_move, opera_moves

FACTS: dict[str, Any] = {
    "move_san": "Nf6",
    "best_move_san": "Qf6",
    "refutation_line_san": ["Qb3", "Bc5", "Bxf7+", "Ke7", "O-O"],
    "motifs_in_refutation": [{"type": "fork", "piece": "N", "square": "e7", "targets": ["Kg8"]}],
}
GROUNDED = grounded_tokens(FACTS)

# --- Проверка SAN ---


@pytest.mark.parametrize(
    "text",
    [
        "Ход Nf6 ошибочен: после Qb3 белые атакуют f7, лучше было Qf6.",
        "After Bxf7 the king must go to Ke7.",  # шах в фактах есть, в тексте нет
        "Белые могли сыграть 0-0, а конь e7 бьёт короля g8 (Kg8).",
        "Счёт 1-0, оценка +2.63, разница 1.5 пешки, ход 12.",
        "No moves here at all.",
    ],
)
def test_grounded_text_passes(text: str) -> None:
    assert invalid_moves(text, GROUNDED) == []


@pytest.mark.parametrize(
    ("text", "invalid"),
    [
        ("Лучше было Qh5, а не Nf6.", ["Qh5"]),
        ("After Nxe5 dxe5 everything collapses.", ["Nxe5", "dxe5"]),
        ("Пешка идёт на h4.", ["h4"]),  # поля h4 в фактах нет
        ("Better was e8=Q+ and O-O-O.", ["e8=Q+", "O-O-O"]),
        ("Лучше было Кf3 или Фd1.", ["Кf3", "Фd1"]),  # русская нотация запрещена
        ("Qh5 и снова Qh5+", ["Qh5", "Qh5+"]),
    ],
)
def test_hallucinated_moves_are_found(text: str, invalid: list[str]) -> None:
    assert invalid_moves(text, GROUNDED) == invalid


def test_mentioned_moves_and_normalize() -> None:
    assert mentioned_moves("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4") == [
        "e4",
        "e5",
        "Nf3",
        "Nc6",
        "Bb5",
        "a6",
        "Ba4",
    ]
    assert mentioned_moves("Kxf7+ R1e2 axb8=Q# Qh4xe1") == ["Kxf7+", "R1e2", "axb8=Q#", "Qh4xe1"]
    assert normalize("Bxf7+") == "Bxf7"
    assert normalize("0-0-0") == "O-O-O"
    assert normalize("Rd8#") == "Rd8"


# --- Шаблоны ---


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_templates_only_use_grounded_moves(lang: templates.Lang) -> None:
    """Шаблон — запасной вариант при галлюцинациях: сам он проверку проходит всегда."""
    for move in opera_moves():
        facts = move_facts(move)
        if facts is None:
            continue
        text = templates.explain_move(facts, lang)
        assert text
        assert invalid_moves(text, grounded_tokens(facts)) == [], text
    summary = game_facts(opera_info(), opera_moves())
    text = templates.summarize_game(summary, lang)
    assert invalid_moves(text, grounded_tokens(summary)) == [], text


def test_move_templates() -> None:
    nf6 = move_facts(opera_move("Nf6"))
    qe7 = move_facts(opera_move("Qe7"))
    rxd7 = move_facts(opera_move("Rxd7"))
    qb3 = move_facts(opera_move("Qb3"))
    assert nf6 is not None
    assert qe7 is not None
    assert rxd7 is not None
    assert qb3 is not None

    assert templates.explain_move(nf6, "ru") == (
        "Ошибка: 6... Nf6, оценка -1.31 → -2.63. Соперник отвечает Qb3, "
        "потеря материала: 1 пешка. Лучше было Qf6."
    )
    assert templates.explain_move(nf6, "en") == (
        "Mistake: 6... Nf6, evaluation -1.31 → -2.63. The opponent replies Qb3, "
        "losing 1 pawn. Better was Qf6."
    )
    assert "пойманная фигура (ферзь b7 → ладья a8; выигрыш 1 пешка)" in templates.explain_move(
        qe7, "ru"
    )
    assert templates.explain_move(rxd7, "en").startswith("13. Rxd7 is a brilliant sacrifice on d7")
    assert templates.explain_move(qb3, "ru").startswith("7. Qb3 — сильнейший ход")


def test_miss_and_unknown_class_templates() -> None:
    facts = {
        "move_number": 20,
        "color": "white",
        "move_san": "Kf1",
        "class": "good",
        "is_miss": True,
        "eval_before": "+3.00",
        "eval_after": "+0.50",
        "best_move_san": "Qxd8",
        "motifs_missed": [{"type": "mate_in_n", "n": 3}],
    }

    ru = templates.explain_move(facts, "ru")
    en = templates.explain_move(facts, "en")

    assert ru == (
        "20. Kf1: +3.00 → +0.50. Соперник только что ошибся, но шанс наказать его упущен. "
        "Лучше было Qxd8 — мат в 3 хода."
    )
    assert en.endswith("Better was Qxd8 — mate in 3.")


@pytest.mark.parametrize(
    ("n", "word"),
    [
        (1, "пешка"),
        (2, "пешки"),
        (5, "пешек"),
        (11, "пешек"),
        (12, "пешек"),
        (21, "пешка"),
        (22, "пешки"),
        (114, "пешек"),
    ],
)
def test_plural_ru(n: int, word: str) -> None:
    assert templates.pawns(n, "ru") == f"{n} {word}"


def test_describe_motif() -> None:
    fork = {"type": "fork", "piece": "N", "square": "e7", "targets": ["Kg8", "Rc8"]}

    assert templates.describe_motif(fork, "ru") == "вилка (конь e7 → король g8, ладья c8)"
    assert templates.describe_motif(fork, "en") == "fork (knight e7 → king g8, rook c8)"
    assert templates.describe_motif({"type": "pin", "piece": "B", "square": "b5"}, "en") == (
        "pin (bishop b5)"
    )
    assert templates.describe_motif({"type": "new_motif"}, "ru") == "new motif"
    assert templates.describe_motif({"type": "mate_in_n", "n": 1}, "ru") == "мат в 1 ход"
    assert templates.pawns(1, "en") == "1 pawn"


def test_simple_texts() -> None:
    assert templates.explain_simple("book", "ru") == "Ход из дебютной теории."
    assert templates.explain_simple("best", "en") == "The engine's top choice."
    assert templates.explain_simple("blunder", "en") == "Blunder."


def test_summary_templates() -> None:
    facts = game_facts(opera_info(), opera_moves())

    ru = templates.summarize_game(facts, "ru").splitlines()
    en = templates.summarize_game(facts, "en").splitlines()

    assert 3 <= len(ru) <= 5
    assert all(line.startswith("- ") for line in ru + en)
    assert ru[0].startswith("- Точность: Paul Morphy (белые) — 88.3%")
    assert "- Перелом: 6... Nf6 (ошибка), -1.31 → -2.63; лучше было Qf6." in ru
    assert en[2] == "- Turning point: 6... Nf6 (mistake), -1.31 → -2.63; better was Qf6."

    clean: dict[str, Any] = {
        "players": {
            color: {
                "name": color,
                "accuracy": None,
                "errors": {"inaccuracy": 0},
                "typical_errors": [],
                "phase_accuracy": {},
            }
            for color in ("white", "black")
        },
        "key_moments": [],
        "user_color": None,
    }
    assert templates.summarize_game(clean, "en") == "- A clean game without clear errors."
