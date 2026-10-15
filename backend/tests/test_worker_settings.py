"""Настройки ARQ-воркера: задача анализа зарегистрирована, пул движков стартует и гасится."""

from typing import Any

import pytest

from app.workers import imports
from app.workers import settings as worker_settings
from app.workers.analysis import TASK_NAME


def test_analysis_task_is_registered() -> None:
    functions = {f.name: f for f in worker_settings.WorkerSettings.functions}

    assert TASK_NAME in functions
    assert functions[TASK_NAME].timeout_s == worker_settings.settings.analysis_job_timeout_s
    assert worker_settings.WorkerSettings.max_jobs == worker_settings.settings.worker_max_jobs
    assert functions[imports.TASK_NAME].timeout_s == worker_settings.settings.import_job_timeout_s


async def test_startup_starts_engine_pool(
    stockfish_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        worker_settings,
        "settings",
        worker_settings.settings.model_copy(
            update={"stockfish_path": stockfish_path, "engine_pool_size": 1}
        ),
    )
    ctx: dict[str, Any] = {}

    await worker_settings.startup(ctx)
    try:
        assert ctx["engine_version"].startswith("Stockfish")
        assert len(ctx["engine"].pids) == 1
        assert ctx["http"].headers["User-Agent"] == worker_settings.settings.import_user_agent
    finally:
        await worker_settings.shutdown(ctx)

    assert ctx["engine"].pids == []
    assert ctx["http"].is_closed
