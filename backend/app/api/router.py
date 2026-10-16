from fastapi import APIRouter

from app.api import (
    analyses,
    auth,
    browser,
    engine,
    explain,
    games,
    imports,
    puzzles,
    shared,
    stats,
)

# Роуты §8.
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(games.router)
api_router.include_router(analyses.router)
api_router.include_router(imports.router)
api_router.include_router(explain.router)
api_router.include_router(stats.router)
api_router.include_router(puzzles.router)
# Сессия 11: публичные ссылки на разбор (без входа) и управление ими.
api_router.include_router(shared.router)
api_router.include_router(browser.router)
api_router.include_router(engine.router)
