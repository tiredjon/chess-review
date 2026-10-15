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

# book: позиция после хода в книге и ход не позже этого полного хода.
BOOK_MAX_FULLMOVE = 15
# brilliant: ход лучший или теряет не больше стольких win%…
BRILLIANT_MAX_DELTA = 2.0
# …оценка после хода не хуже этого (cp, с точки зрения ходящего)…
BRILLIANT_MIN_EVAL_CP = -100
# …и до хода игрок ещё не выигрывал подавляюще (win% строго меньше).
BRILLIANT_MAX_WIN_BEFORE = 97.0
# Жертва: в PV1 материал ходящего временно падает хотя бы на столько пешек.
SACRIFICE_MIN_MATERIAL_DROP = 2
# …и соперник берёт отданную фигуру не позже стольких своих ходов в PV1.
SACRIFICE_ACCEPT_MOVES = 2
# great: лучший ход, а второй вариант MultiPV хуже хотя бы на столько win%…
GREAT_MIN_GAP = 10.0
# …или лучший ход меняет результат: проигрыш — win% < LOSING_MAX_WIN,
# выигрыш — win% > WINNING_MIN_WIN, между ними — ничья.
LOSING_MAX_WIN = 20.0
WINNING_MIN_WIN = 80.0
# miss: соперник ошибся (mistake/blunder), а игрок потерял хотя бы столько win%.
MISS_MIN_DELTA = 10.0
