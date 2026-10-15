"""Провайдеры LLM: выбор по настройкам, параметры запросов к SDK, ошибки → LLMError.

Сеть не трогается: методы SDK подменяются, проверяется, что именно им передаётся.
"""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import openai
import pytest
from google.genai import errors as genai_errors
from pydantic import SecretStr

from app.core.config import LLMProviderName, Settings
from app.explain.llm import (
    AnthropicProvider,
    GeminiProvider,
    LLMError,
    OpenAIProvider,
    make_provider,
)


class Recorder:
    """Подмена метода SDK: запоминает аргументы, отдаёт ответ или бросает исключение."""

    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_make_provider_none_and_missing_key() -> None:
    assert make_provider(Settings(llm_provider=LLMProviderName.NONE)) is None
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        make_provider(Settings(llm_provider=LLMProviderName.GEMINI, gemini_api_key=None))
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        make_provider(Settings(llm_provider=LLMProviderName.OPENAI, openai_api_key=SecretStr("")))


@pytest.mark.parametrize(
    ("name", "field", "cls", "model"),
    [
        (LLMProviderName.GEMINI, "gemini_api_key", GeminiProvider, "gemini-3.1-flash-lite"),
        (LLMProviderName.OPENAI, "openai_api_key", OpenAIProvider, "gpt-5-nano"),
        (LLMProviderName.ANTHROPIC, "anthropic_api_key", AnthropicProvider, "claude-haiku-5-5"),
    ],
)
async def test_make_provider_defaults(
    name: LLMProviderName, field: str, cls: type[Any], model: str
) -> None:
    provider = make_provider(Settings.model_validate({"llm_provider": name, field: "key"}))
    custom = make_provider(
        Settings.model_validate({"llm_provider": name, "llm_model": "custom-model", field: "key"})
    )

    assert isinstance(provider, cls)
    assert provider.model == model
    assert provider.name == name.value
    assert custom is not None
    assert custom.model == "custom-model"
    await provider.close()
    await custom.close()


async def test_gemini_request_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GeminiProvider("key", "gemini-test", timeout_s=5)
    models = provider.client.aio.models
    ok = Recorder(SimpleNamespace(text="  Объяснение.  "))
    monkeypatch.setattr(models, "generate_content", ok)

    assert await provider.generate("system", "user", 100) == "Объяснение."
    (call,) = ok.calls
    assert call["model"] == "gemini-test"
    assert call["contents"] == "user"
    assert call["config"].system_instruction == "system"
    assert call["config"].max_output_tokens == 100

    monkeypatch.setattr(models, "generate_content", Recorder(SimpleNamespace(text=None)))
    with pytest.raises(LLMError, match="gemini: пустой ответ"):
        await provider.generate("s", "u", 10)
    error = genai_errors.ServerError(503, {"error": {"message": "overloaded"}})
    monkeypatch.setattr(models, "generate_content", Recorder(error))
    with pytest.raises(LLMError, match="Gemini"):
        await provider.generate("s", "u", 10)
    await provider.close()


async def test_openai_request_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAIProvider("key", "gpt-test", timeout_s=5)
    ok = Recorder(SimpleNamespace(output_text="Text."))
    monkeypatch.setattr(provider.client.responses, "create", ok)

    assert await provider.generate("system", "user", 200) == "Text."
    (call,) = ok.calls
    assert call == {
        "model": "gpt-test",
        "instructions": "system",
        "input": "user",
        "max_output_tokens": 200,
        "reasoning": {"effort": "minimal"},
    }

    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.APIConnectionError(request=request)
    monkeypatch.setattr(provider.client.responses, "create", Recorder(error))
    with pytest.raises(LLMError, match="OpenAI"):
        await provider.generate("s", "u", 10)
    await provider.close()


def anthropic_message(*blocks: Any, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


async def test_anthropic_request_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AnthropicProvider("key", "claude-test", timeout_s=5)
    thinking = SimpleNamespace(type="thinking", thinking="")
    ok = Recorder(
        anthropic_message(
            thinking,
            SimpleNamespace(type="text", text="Part one. "),
            SimpleNamespace(type="text", text="Part two."),
        )
    )
    monkeypatch.setattr(provider.client.messages, "create", ok)

    assert await provider.generate("system", "user", 300) == "Part one. Part two."
    (call,) = ok.calls
    assert call == {
        "model": "claude-test",
        "max_tokens": 300,
        "system": "system",
        "messages": [{"role": "user", "content": "user"}],
        "output_config": {"effort": "low"},
    }

    refusal = Recorder(anthropic_message(stop_reason="refusal"))
    monkeypatch.setattr(provider.client.messages, "create", refusal)
    with pytest.raises(LLMError, match="отказ"):
        await provider.generate("s", "u", 10)

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(request=request)
    monkeypatch.setattr(provider.client.messages, "create", Recorder(error))
    with pytest.raises(LLMError, match="Anthropic"):
        await provider.generate("s", "u", 10)
    await provider.close()
