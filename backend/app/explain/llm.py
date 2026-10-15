"""Провайдеры LLM (SPEC §6.2): `LLMProvider.generate(system, user, max_tokens) -> str`.

Выбор — `LLM_PROVIDER` (none | gemini | openai | anthropic), модель — `LLM_MODEL`,
по умолчанию самая дешёвая быстрая модель провайдера. Любая ошибка провайдера
(сеть, лимиты, отказ, пустой ответ) — `LLMError`: вызывающий переходит на шаблоны.
"""

from typing import Protocol

import anthropic
import openai
import structlog
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.core.config import LLMProviderName, Settings

log = structlog.get_logger(__name__)

DEFAULT_MODELS = {
    LLMProviderName.GEMINI: "gemini-3.1-flash-lite",
    LLMProviderName.OPENAI: "gpt-5-nano",
    LLMProviderName.ANTHROPIC: "claude-haiku-5-5",
}


class LLMError(Exception):
    """Провайдер не дал пригодного ответа."""


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(self, system: str, user: str, max_tokens: int) -> str: ...

    async def close(self) -> None: ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        self.model = model
        self.client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=int(timeout_s * 1000)),
        )

    async def generate(self, system: str, user: str, max_tokens: int) -> str:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system, max_output_tokens=max_tokens
                ),
            )
        except genai_errors.APIError as exc:
            raise LLMError(f"Gemini: {exc}") from exc
        return _text(self.name, response.text)

    async def close(self) -> None:
        await self.client.aio.aclose()


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        self.model = model
        self.client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout_s, max_retries=1)

    async def generate(self, system: str, user: str, max_tokens: int) -> str:
        try:
            response = await self.client.responses.create(
                model=self.model,
                instructions=system,
                input=user,
                max_output_tokens=max_tokens,
                # Объяснение по готовым фактам — рассуждать почти не о чем.
                reasoning={"effort": "minimal"},
            )
        except openai.OpenAIError as exc:
            raise LLMError(f"OpenAI: {exc}") from exc
        return _text(self.name, response.output_text)

    async def close(self) -> None:
        await self.client.close()


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s, max_retries=1)

    async def generate(self, system: str, user: str, max_tokens: int) -> str:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                # Короткий текст по готовым фактам: глубокое рассуждение не нужно.
                output_config={"effort": "low"},
            )
        except anthropic.APIError as exc:
            raise LLMError(f"Anthropic: {exc}") from exc
        if response.stop_reason == "refusal":
            raise LLMError("Anthropic: отказ модели")
        text = "".join(block.text for block in response.content if block.type == "text")
        return _text(self.name, text)

    async def close(self) -> None:
        await self.client.close()


def _text(provider: str, text: str | None) -> str:
    text = (text or "").strip()
    if not text:
        raise LLMError(f"{provider}: пустой ответ")
    return text


def make_provider(settings: Settings) -> LLMProvider | None:
    """Провайдер из настроек; None — `LLM_PROVIDER=none` (шаблонные объяснения)."""
    name = settings.llm_provider
    if name == LLMProviderName.NONE:
        return None
    key = {
        LLMProviderName.GEMINI: settings.gemini_api_key,
        LLMProviderName.OPENAI: settings.openai_api_key,
        LLMProviderName.ANTHROPIC: settings.anthropic_api_key,
    }[name]
    api_key = key.get_secret_value() if key else ""
    if not api_key:
        raise ValueError(f"LLM_PROVIDER={name}, но ключ {name.upper()}_API_KEY не задан")
    model = settings.llm_model or DEFAULT_MODELS[name]
    providers: dict[LLMProviderName, type[GeminiProvider | OpenAIProvider | AnthropicProvider]] = {
        LLMProviderName.GEMINI: GeminiProvider,
        LLMProviderName.OPENAI: OpenAIProvider,
        LLMProviderName.ANTHROPIC: AnthropicProvider,
    }
    log.info("llm.provider", provider=str(name), model=model)
    return providers[name](api_key, model, settings.llm_timeout_s)
