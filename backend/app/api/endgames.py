"""Тренажёр эндшпиля (сессия 16.3): позиции из своих партий, таблицы Syzygy, попытки.

Фундамент: заглушка роутера. Контракт — SPEC «Сессия 16», реализация — 16.3.
"""

from fastapi import APIRouter

router = APIRouter(tags=["endgames"])
