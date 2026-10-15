from fastapi import APIRouter

from app.api import analyses, explain, games, imports

# Роуты §8; stats, puzzles подключаются в следующих сессиях.
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(games.router)
api_router.include_router(analyses.router)
api_router.include_router(imports.router)
api_router.include_router(explain.router)
