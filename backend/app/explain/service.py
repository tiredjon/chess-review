"""Объяснения: факты → кэш → LLM (с проверкой SAN и одним повтором) → шаблон.

Порядок (SPEC §6.2):
1. Факты хода / партии (`facts.py`); для необъясняемых ходов — короткий шаблон.
2. Без провайдера (`LLM_PROVIDER=none`) — шаблон; он мгновенный, в кэш не пишется.
3. Кэш `explanations` по хешу фактов + язык; в хеш входят версия промпта,
   провайдер и модель — смена любого из них даёт новые объяснения.
4. Ответ LLM с ходами не из фактов — один повтор с указанием ошибки, затем шаблон.
   Такой шаблон кэшируется (провайдер "template"), чтобы не платить за тот же
   провал снова. Ошибка провайдера (сеть, лимиты) — шаблон без кэша: в следующий
   раз LLM попробуем снова.
"""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Explanation
from app.explain import prompts, templates
from app.explain.facts import (
    GameInfo,
    MoveLike,
    facts_hash,
    game_facts,
    grounded_tokens,
    move_facts,
)
from app.explain.llm import LLMError, LLMProvider
from app.explain.templates import Lang
from app.explain.validate import invalid_moves

log = structlog.get_logger(__name__)

TEMPLATE = "template"
# С запасом: у части моделей в лимит входят и токены рассуждения.
MOVE_MAX_TOKENS = 2048
SUMMARY_MAX_TOKENS = 3072


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    text: str
    # "template" или имя провайдера LLM.
    provider: str
    cached: bool = False


class Explainer:
    def __init__(
        self,
        provider: LLMProvider | None,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        concurrency: int = 4,
    ) -> None:
        self.provider = provider
        self.sessionmaker = sessionmaker
        self._limit = asyncio.Semaphore(concurrency)

    async def explain_move(self, move: MoveLike, lang: Lang) -> ExplanationResult:
        facts = move_facts(move)
        if facts is None:
            return ExplanationResult(
                templates.explain_simple(move.move_class.value, lang), TEMPLATE
            )
        return await self._explain(
            "move",
            facts,
            lang,
            system=prompts.move_system(lang),
            user=prompts.move_user(facts),
            max_tokens=MOVE_MAX_TOKENS,
            fallback=lambda: templates.explain_move(facts, lang),
        )

    async def explain_moves(self, moves: Sequence[MoveLike], lang: Lang) -> list[ExplanationResult]:
        """Пакет объяснений (при открытии разбора); запросов к LLM — не больше `concurrency`."""

        async def one(move: MoveLike) -> ExplanationResult:
            async with self._limit:
                return await self.explain_move(move, lang)

        return list(await asyncio.gather(*(one(move) for move in moves)))

    async def summarize(
        self, game: GameInfo, moves: Sequence[MoveLike], lang: Lang
    ) -> ExplanationResult:
        facts = game_facts(game, moves)
        return await self._explain(
            "summary",
            facts,
            lang,
            system=prompts.summary_system(lang),
            user=prompts.summary_user(facts),
            max_tokens=SUMMARY_MAX_TOKENS,
            fallback=lambda: templates.summarize_game(facts, lang),
        )

    async def _explain(
        self,
        kind: str,
        facts: Mapping[str, Any],
        lang: Lang,
        *,
        system: str,
        user: str,
        max_tokens: int,
        fallback: Callable[[], str],
    ) -> ExplanationResult:
        provider = self.provider
        if provider is None:
            return ExplanationResult(fallback(), TEMPLATE)
        salt = f"{prompts.PROMPT_VERSION}:{kind}:{provider.name}:{provider.model}"
        key = facts_hash(facts, salt=salt)
        cached = await self._cached(key, lang)
        if cached is not None:
            return ExplanationResult(cached.text, cached.provider, cached=True)

        grounded = grounded_tokens(facts)
        prompt = user
        for attempt in (1, 2):
            try:
                text = await provider.generate(system, prompt, max_tokens)
            except LLMError as exc:
                log.warning("explain.llm_failed", kind=kind, error=str(exc))
                return ExplanationResult(fallback(), TEMPLATE)
            invalid = invalid_moves(text, grounded)
            if not invalid:
                await self._store(key, lang, text, provider.name)
                return ExplanationResult(text, provider.name)
            log.warning("explain.invalid_moves", kind=kind, attempt=attempt, moves=invalid)
            prompt = user + prompts.retry_note(invalid)

        text = fallback()
        await self._store(key, lang, text, TEMPLATE)
        return ExplanationResult(text, TEMPLATE)

    async def _cached(self, key: str, lang: Lang) -> Explanation | None:
        async with self.sessionmaker() as session:
            found: Explanation | None = await session.scalar(
                select(Explanation).where(Explanation.facts_hash == key, Explanation.lang == lang)
            )
            return found

    async def _store(self, key: str, lang: Lang, text: str, provider: str) -> None:
        async with self.sessionmaker() as session:
            await session.execute(
                insert(Explanation)
                .values(facts_hash=key, lang=lang, text=text, provider=provider)
                .on_conflict_do_nothing()
            )
            await session.commit()
