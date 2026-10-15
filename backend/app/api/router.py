from fastapi import APIRouter

from app.api import analyses, games

# Роуты §8; imports, explain, stats, puzzles подключаются в следующих сессиях.
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(games.router)
api_router.include_router(analyses.router)
