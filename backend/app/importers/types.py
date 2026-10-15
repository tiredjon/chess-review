from dataclasses import dataclass
from datetime import datetime

from app.db.models import Color


@dataclass(frozen=True, slots=True)
class ImportedGame:
    """Партия из любого источника, готовая к сохранению в `games`."""

    external_id: str
    pgn: str
    white: str
    black: str
    white_elo: int | None
    black_elo: int | None
    result: str
    time_control: str | None
    played_at: datetime | None
    opening_eco: str | None
    opening_name: str | None
    # None — источник не знает; тогда цвет ищется по никам пользователя.
    user_color: Color | None = None
    # Точность по версии площадки (Chess.com отдаёт её у партий, разобранных там).
    source_white_accuracy: float | None = None
    source_black_accuracy: float | None = None
