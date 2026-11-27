"""Эталоны рейтинговых групп (SPEC «Сессия 17», 17.1): выборка игроков Chess.com, анализ их
партий нашим конвейером и сборка агрегатов в `app/coach/data/{norms,trajectories}.json`.

Команды (все возобновляемые, прогресс — в отдельной БД `chess_review_norms`):

    python -m app.coach.norms crawl    # игроки и партии с публичного API Chess.com
    python -m app.coach.norms analyze  # анализ отобранных партий (Stockfish, глубина по умолчанию)
    python -m app.coach.norms build    # агрегаты → JSON (в git — только они)

Рабочая БД `chess_review` только читается (семена — соперники из партий Chess.com).
Ники и партии чужих игроков остаются в `chess_review_norms` и в репозиторий не попадают.
"""

from dataclasses import dataclass

from app.review.game_rating import TimeClass

# Контроли эталона: буллет сравнивается с блицем, daily — с рапидом (SPEC).
NORM_TIME_CLASSES: tuple[TimeClass, ...] = ("rapid", "blitz")
NORM_FALLBACK: dict[str, TimeClass] = {"bullet": "blitz", "daily": "rapid"}

BAND_MIN, BAND_MAX, BAND_STEP, BAND_HALF_WIDTH = 800, 2600, 100, 100
BAND_CENTERS: tuple[int, ...] = tuple(range(BAND_MIN, BAND_MAX + 1, BAND_STEP))
# Собираемые группы (решение оркестратора и пользователя, 2026-11-27): сначала рапид, затем
# блиц, центры 1500–2200. Остальные центры (800–1400, 2300–2600) пока не собираются: в
# `norms.json` их нет, диагностика берёт ближайшую группу и помечает, что она далеко.
PRIORITY_BANDS: tuple[int, ...] = tuple(range(1500, 2201, 100))
STAGES: tuple[TimeClass, ...] = ("rapid", "blitz")


@dataclass(frozen=True, slots=True)
class SampleTargets:
    """Сколько набирать в «ближайшую» группу (рейтинг ближе всего к центру). Группы эталона
    шире (±100), поэтому в сборке на группу приходится больше; квота — ≥ 30 игроков
    и ≥ 150 партий на группу."""

    players: int = 30
    games_per_player: int = 5
    # Сколько последних месяцев с партиями просматривать ради выборки.
    sample_months: int = 2
    # Траектории: архивы не старше стольких месяцев, через `trajectory_stride` месяцев.
    trajectory_months: int = 36
    trajectory_stride: int = 3


TARGETS = SampleTargets()


def nearest_center(rating: int) -> int | None:
    """Ближайший центр группы; рейтинг за пределами крайних групп (±половина шага) — None."""
    if rating < BAND_MIN - BAND_STEP // 2 or rating >= BAND_MAX + BAND_STEP // 2:
        return None
    return BAND_MIN + (rating - BAND_MIN + BAND_STEP // 2) // BAND_STEP * BAND_STEP
