from fastapi import APIRouter

from app.api import analyses, explain, games, imports, puzzles, stats

# Роуты §8.
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(games.router)
api_router.include_router(analyses.router)
api_router.include_router(imports.router)
api_router.include_router(explain.router)
api_router.include_router(stats.router)
api_router.include_router(puzzles.router)
