"""Разбор последней партии по нику: источник → `games` → анализ → отчёт.

Партии из бота принадлежат системному пользователю (`BOT_USER_ID`, сид в миграции):
партии Lichess / Chess.com публичны, а одна и та же партия по разным запросам
сохраняется и анализируется один раз (unique(source, external_id, user_id)).
Ссылка в ответе — публичная (`/share/{token}`).
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import structlog
from sqlalchemy import select

from app.api.schemas import AnalysisSummary, GameOut
from app.bot.report import GameReport, key_mistakes
from app.bot.runner import AnalysisRunner
from app.core.config import Settings
from app.core.errors import ErrorCode
from app.db.models import Analysis, AnalysisStatus, Color, Game, GameSource, Move, User
from app.db.models import AnalysisRunner as RunnerKind
from app.db.session import Database
from app.db.share import ensure_share_token, share_url
from app.explain.rows import game_info
from app.explain.service import Explainer
from app.explain.templates import Lang
from app.importers.chesscom import ChessComClient
from app.importers.http import RetryPolicy
from app.importers.lichess import LichessClient
from app.importers.sources import SourceGame, convert_page
from app.importers.store import save_games, user_color
from app.importers.types import ImportedGame

log = structlog.get_logger(__name__)

# Chess.com: последний месяц с партиями и предыдущий (если в последнем только варианты).
CHESSCOM_ARCHIVES = 2


class BotError(Exception):
    """Понятная пользователю ошибка: код — `app/core/errors.py`, текст — `texts.py`."""

    def __init__(self, code: ErrorCode, detail: str = "") -> None:
        super().__init__(detail or code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class _Prepared:
    game_id: uuid.UUID
    analysis_id: uuid.UUID
    status: AnalysisStatus
    url: str


class ReviewService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        http: httpx.AsyncClient,
        runner: AnalysisRunner,
        explainer: Explainer,
        *,
        policy: RetryPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.http = http
        self.runner = runner
        self.explainer = explainer
        self.policy = policy or RetryPolicy.from_settings(settings)

    async def review_last_game(self, source: GameSource, username: str, lang: Lang) -> GameReport:
        """Разбор последней партии `username`; ошибки источника — BotError."""
        imported = await self.last_game(source, username)
        color = user_color(imported, [username])
        prepared = await self._prepare(source, imported)
        log_ = log.bind(game_id=str(prepared.game_id), analysis_id=str(prepared.analysis_id))
        if prepared.status != AnalysisStatus.DONE:
            log_.info("bot.analysis_wait", status=prepared.status)
            try:
                async with asyncio.timeout(self.settings.bot_analysis_timeout_s):
                    await self.runner.run(prepared.analysis_id)
            except TimeoutError:
                # Анализ продолжается в воркере: ответ — ссылка, там будет результат.
                log_.info("bot.analysis_timeout")
        return await self._report(prepared, color, lang)

    async def last_game(self, source: GameSource, username: str) -> ImportedGame:
        """Последняя партия в классические шахматы; цвет — по `username`."""
        # Между страницами генератор ничего не держит открытым: бросить его можно.
        async for page in self._pages(source, username):
            # Разбор PGN и поиск дебюта — CPU.
            games = await asyncio.to_thread(convert_page, page, username)
            if games:
                return games[0]
        raise BotError(ErrorCode.SOURCE_NO_GAMES)

    def _pages(self, source: GameSource, username: str) -> AsyncIterator[list[SourceGame]]:
        settings = self.settings
        if source == GameSource.LICHESS:
            token = settings.lichess_token.get_secret_value() if settings.lichess_token else None
            lichess = LichessClient(
                self.http,
                base_url=settings.lichess_api_url,
                token=token or None,
                policy=self.policy,
            )
            return lichess.games(username, 1)
        if source == GameSource.CHESSCOM:
            chesscom = ChessComClient(
                self.http, base_url=settings.chesscom_api_url, policy=self.policy
            )
            return chesscom.recent(username, archives=CHESSCOM_ARCHIVES)
        raise ValueError(f"Бот не умеет {source}")

    async def _prepare(self, source: GameSource, imported: ImportedGame) -> _Prepared:
        """Партия бота, ссылка и анализ глубины ANALYSIS_DEPTH: существующий (не failed)
        или новый в queued — как `POST /games/{id}/analyze`."""
        depth = self.settings.analysis_depth
        async with self.db.sessionmaker() as session:
            bot_user = await session.get(User, self.settings.bot_user_id)
            if bot_user is None:
                raise RuntimeError("Нет пользователя бота (BOT_USER_ID): примените миграции")
            (saved,) = await save_games(session, bot_user, source, [imported])
            await session.commit()
            # Блокировка партии: параллельные запросы не создадут два анализа и две ссылки.
            game = await session.scalar(select(Game).where(Game.id == saved.id).with_for_update())
            assert game is not None
            token = ensure_share_token(game)
            analysis = await session.scalar(
                select(Analysis)
                .where(
                    Analysis.game_id == game.id,
                    Analysis.depth == depth,
                    Analysis.runner == RunnerKind.SERVER,
                    Analysis.status != AnalysisStatus.FAILED,
                )
                .order_by(Analysis.created_at.desc())
                .limit(1)
            )
            if analysis is None:
                analysis = Analysis(game_id=game.id, depth=depth, status=AnalysisStatus.QUEUED)
                session.add(analysis)
            await session.commit()
            return _Prepared(game.id, analysis.id, analysis.status, share_url(self.settings, token))

    async def _report(self, prepared: _Prepared, color: Color | None, lang: Lang) -> GameReport:
        async with self.db.sessionmaker() as session:
            game = await session.get(Game, prepared.game_id)
            analysis = await session.get(Analysis, prepared.analysis_id)
            assert game is not None
            assert analysis is not None
            out = GameOut.model_validate(game)
            out.analysis = AnalysisSummary.model_validate(analysis)
            moves: list[Move] = []
            if analysis.status == AnalysisStatus.DONE:
                moves = list(
                    await session.scalars(
                        select(Move).where(Move.analysis_id == analysis.id).order_by(Move.ply)
                    )
                )
        summary = None
        if analysis.status == AnalysisStatus.DONE:
            try:
                info = game_info(game, analysis, user_color=color)
                summary = (await self.explainer.summarize(info, moves, lang)).text
            except Exception:
                # Итог — дополнение: без него ответ всё равно полезен.
                log.exception("bot.summary_failed", analysis_id=str(analysis.id))
        return GameReport(
            game=out,
            color=color,
            status=analysis.status,
            mistakes=key_mistakes(moves, color) if color is not None else [],
            summary=summary,
            url=prepared.url,
        )
