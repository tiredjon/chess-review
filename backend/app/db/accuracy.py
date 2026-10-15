"""Какую точность показывать за игрока — единственное место, где задан порядок источников.

Порядок: официальная точность площадки (Chess.com — у партий, разобранных там) → наша
«как у Chess.com» (`review/cc_accuracy.py`) → по формуле Lichess (у старых анализов без cc).
Две последние — только у готового анализа. Из этого списка строятся и выбор по ORM-объектам
(`GameOut.accuracy_of`, плашки), и SQL-выражение для агрегатов статистики.
"""

from typing import Any, Literal, Protocol

from sqlalchemy import ColumnElement, case, func, literal, null
from sqlalchemy.sql.expression import FromClause

from app.db.models import AnalysisStatus, Color

AccuracyKind = Literal["official", "cc", "lichess"]

# (вид, таблица, колонка с `{color}`).
SOURCES: tuple[tuple[AccuracyKind, Literal["game", "analysis"], str], ...] = (
    ("official", "game", "source_{color}_accuracy"),
    ("cc", "analysis", "cc_{color}_accuracy"),
    ("lichess", "analysis", "{color}_accuracy"),
)


class _HasStatus(Protocol):
    @property
    def status(self) -> AnalysisStatus: ...


def pick_accuracy(
    game: object, analysis: _HasStatus | None, color: Color
) -> tuple[float, AccuracyKind] | None:
    """Точность игрока `color` и её вид; None — точности нет."""
    done = analysis is not None and analysis.status == AnalysisStatus.DONE
    for kind, table, template in SOURCES:
        source = game if table == "game" else (analysis if done else None)
        if source is None:
            continue
        value = getattr(source, template.format(color=color.value))
        if value is not None:
            return float(value), kind
    return None


def _candidates(
    game: FromClause, analysis: FromClause, color: ColumnElement[Any]
) -> list[tuple[AccuracyKind, ColumnElement[Any]]]:
    """SQL-значение каждого источника за игрока с цветом `color` (колонка `games.user_color`)."""
    done = analysis.c.status == AnalysisStatus.DONE
    result: list[tuple[AccuracyKind, ColumnElement[Any]]] = []
    for kind, table, template in SOURCES:
        source = game if table == "game" else analysis
        white = source.c[template.format(color="white")]
        black = source.c[template.format(color="black")]
        value = case((color == Color.WHITE, white), else_=black)
        if table == "analysis":
            value = case((done, value), else_=null())
        result.append((kind, value))
    return result


def accuracy_sql(
    game: FromClause, analysis: FromClause, color: ColumnElement[Any]
) -> tuple[ColumnElement[float | None], ColumnElement[str | None]]:
    """(точность, вид) для SQL: `analysis` — последний анализ партии (LEFT JOIN)."""
    candidates = _candidates(game, analysis, color)
    value = func.coalesce(*(expr for _, expr in candidates))
    kind = case(*((expr.is_not(None), literal(name)) for name, expr in candidates), else_=null())
    return value, kind
