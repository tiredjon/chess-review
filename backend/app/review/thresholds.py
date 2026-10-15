"""Все пороги доменной логики в одном месте (SPEC §4)."""

# --- Оценка → win% (§4.1, §4.2) ---
# Мат в N переводится в cp = ±(MATE_CP − N·MATE_STEP_CP); для win% всё равно обрезается.
MATE_CP = 10_000
MATE_STEP_CP = 10
# cp обрезается до [−CP_CEILING, CP_CEILING] перед формулой win%.
CP_CEILING = 1000
# Оценка стартовой позиции, если анализа для неё нет (как Eval.Cp.initial в lila).
INITIAL_CP = 15

# --- Точность партии (§4.4) ---
VOLATILITY_WINDOW_MIN = 2
VOLATILITY_WINDOW_MAX = 8
VOLATILITY_WEIGHT_MIN = 0.5
VOLATILITY_WEIGHT_MAX = 12.0

# --- Фазы (§4.6) ---
# Дебют длится не дольше этого полного хода (номера ходов — полные ходы).
OPENING_MAX_FULLMOVE = 12
# Эндшпиль: материал без пешек за обе стороны ≤ этого значения (Ф=9, Л=5, С/К=3)…
ENDGAME_MAX_MATERIAL = 13
# …или ферзей нет и лёгких/тяжёлых фигур за обе стороны ≤ этого числа.
ENDGAME_MAX_PIECES_WITHOUT_QUEENS = 6

# --- Классификация (§4.5): максимальная потеря win% для класса ---
EXCELLENT_MAX_DELTA = 2.0
GOOD_MAX_DELTA = 5.0
INACCURACY_MAX_DELTA = 10.0
MISTAKE_MAX_DELTA = 20.0
