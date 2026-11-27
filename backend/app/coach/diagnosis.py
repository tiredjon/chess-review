"""Диагностика тренера (17.1): метрики пользователя против эталонов текущей и целевой группы.

Фундамент: заглушка интерфейса для 17.2. Реализация — 17.1 (SPEC «Сессия 17»).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas_coach import DiagnosisOut
from app.db.models import CoachGoal


async def diagnose(session: AsyncSession, user_id: uuid.UUID, goal: CoachGoal) -> DiagnosisOut:
    raise NotImplementedError("17.1")
