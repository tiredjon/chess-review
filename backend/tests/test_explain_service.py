"""Сервис объяснений: шаблоны без LLM, кэш, повтор и fallback при галлюцинации."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, func, select

from app.db.models import Explanation
from app.db.session import Database
from app.explain import prompts, templates
from app.explain.facts import game_facts, move_facts
from app.explain.llm import LLMError
from app.explain.service import Explainer
from tests.explain_data import opera_info, opera_move, opera_moves

pytestmark = pytest.mark.integration

NF6 = opera_move("Nf6")


class FakeLLM:
    """Провайдер LLM по сценарию: строка — ответ, исключение — ошибка."""

    name = "fake"
    model = "fake-1"

    def __init__(self, *answers: str | Exception, delay: float = 0) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, str, int]] = []
        self.delay = delay
        self.active = 0
        self.max_active = 0

    async def generate(self, system: str, user: str, max_tokens: int) -> str:
        self.calls.append((system, user, max_tokens))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
            answer = self.answers.pop(0) if self.answers else "Ход Nf6 — ошибка."
        finally:
            self.active -= 1
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def close(self) -> None:
        return None


@pytest.fixture
async def explanations(db: Database) -> AsyncIterator[Database]:
    async def clear() -> None:
        async with db.sessionmaker() as session:
            await session.execute(delete(Explanation))
            await session.commit()

    await clear()
    yield db
    await clear()


async def stored(db: Database) -> list[Explanation]:
    async with db.sessionmaker() as session:
        return list(await session.scalars(select(Explanation).order_by(Explanation.id)))


async def test_without_llm_uses_templates(explanations: Database) -> None:
    explainer = Explainer(None, explanations.sessionmaker)

    result = await explainer.explain_move(NF6, "ru")
    simple = await explainer.explain_move(opera_move("e4"), "en")
    summary = await explainer.summarize(opera_info(), opera_moves(), "en")

    facts = move_facts(NF6)
    assert facts is not None
    assert result.text == templates.explain_move(facts, "ru")
    assert result.provider == "template"
    assert not result.cached
    assert simple.text == "A known opening move."
    assert summary.text == templates.summarize_game(game_facts(opera_info(), opera_moves()), "en")
    # Шаблоны мгновенные — в кэш не пишутся.
    assert await stored(explanations) == []


async def test_llm_answer_is_cached_per_language(explanations: Database) -> None:
    llm = FakeLLM("После Nf6 белые играют Qb3, лучше было Qf6.", "After Nf6, Qb3 wins.")
    explainer = Explainer(llm, explanations.sessionmaker)

    first = await explainer.explain_move(NF6, "ru")
    again = await explainer.explain_move(NF6, "ru")
    english = await explainer.explain_move(NF6, "en")

    assert first.text == "После Nf6 белые играют Qb3, лучше было Qf6."
    assert first.provider == "fake"
    assert not first.cached
    assert again.text == first.text
    assert again.cached
    assert english.text == "After Nf6, Qb3 wins."
    assert len(llm.calls) == 2
    system, user, max_tokens = llm.calls[0]
    assert "Ты шахматный тренер" in system
    assert "русский" in system
    assert "English" in llm.calls[1][0]
    assert '"move_san": "Nf6"' in user
    assert max_tokens > 0
    assert {(row.lang, row.provider) for row in await stored(explanations)} == {
        ("ru", "fake"),
        ("en", "fake"),
    }


async def test_hallucinated_move_falls_back_to_template(explanations: Database) -> None:
    """SPEC §11, сессия 7: при галлюцинированном ходе срабатывает fallback."""
    llm = FakeLLM("Лучше было Qh5 с атакой.", "Лучше было Qh5 и Qxf7#.")
    explainer = Explainer(llm, explanations.sessionmaker)

    result = await explainer.explain_move(NF6, "ru")

    facts = move_facts(NF6)
    assert facts is not None
    assert result.text == templates.explain_move(facts, "ru")
    assert result.provider == "template"
    # Один повтор с подсказкой, какие ходы лишние.
    assert len(llm.calls) == 2
    assert llm.calls[1][1].endswith(prompts.retry_note(["Qh5"]))
    # Провал закэширован шаблоном: за ту же галлюцинацию второй раз не платим.
    again = await explainer.explain_move(NF6, "ru")
    assert again.text == result.text
    assert again.cached
    assert len(llm.calls) == 2
    (row,) = await stored(explanations)
    assert row.provider == "template"


async def test_retry_can_fix_the_answer(explanations: Database) -> None:
    llm = FakeLLM("Лучше было Qh5.", "Лучше было Qf6.")
    explainer = Explainer(llm, explanations.sessionmaker)

    result = await explainer.explain_move(NF6, "en")

    assert result.text == "Лучше было Qf6."
    assert result.provider == "fake"


async def test_provider_error_is_not_cached(explanations: Database) -> None:
    llm = FakeLLM(LLMError("timeout"), "Ход Nf6 ошибочен, сильнее Qf6.")
    explainer = Explainer(llm, explanations.sessionmaker)

    failed = await explainer.explain_move(NF6, "ru")
    recovered = await explainer.explain_move(NF6, "ru")

    assert failed.provider == "template"
    assert recovered.provider == "fake"
    assert recovered.text == "Ход Nf6 ошибочен, сильнее Qf6."
    assert len(await stored(explanations)) == 1


async def test_batch_limits_concurrency(explanations: Database) -> None:
    llm = FakeLLM(delay=0.01)
    explainer = Explainer(llm, explanations.sessionmaker, concurrency=2)
    moves = [move for move in opera_moves() if move_facts(move) is not None]

    results = await explainer.explain_moves(moves, "ru")

    assert len(results) == len(moves)
    assert llm.max_active <= 2
    # Ответ «Ход Nf6 — ошибка.» к чужим ходам не подходит — у них шаблон.
    by_san = {move.san: result for move, result in zip(moves, results, strict=True)}
    assert by_san["Nf6"].provider == "fake"
    assert by_san["Rxd7"].provider == "template"


async def test_summary_through_llm(explanations: Database) -> None:
    answer = "- Чёрные ошиблись ходом Nf6.\n- Лучше было Qf6.\n- Точность 85%."
    llm = FakeLLM(answer)
    explainer = Explainer(llm, explanations.sessionmaker)

    result = await explainer.summarize(opera_info(), opera_moves(), "ru")
    again = await explainer.summarize(opera_info(), opera_moves(), "ru")

    assert result.text == answer
    assert again.cached
    assert "3–5 пунктов" in llm.calls[0][0]
    assert '"key_moments"' in llm.calls[0][1]
    async with explanations.sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(Explanation)) == 1
