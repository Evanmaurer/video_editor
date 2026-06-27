import pytest

from montage_backend.models.domain import LlmProviderConfig, LlmProviderType
from montage_backend.services.llm_service import NullLlmProvider, OpenAiProvider, OllamaProvider, create_llm_provider


def test_create_ollama_provider():
    config = LlmProviderConfig(provider=LlmProviderType.OLLAMA, model="qwen3:8b-instruct")
    provider = create_llm_provider(config)
    assert isinstance(provider, OllamaProvider)
    assert provider.provider_name == "ollama"


def test_create_openai_provider():
    config = LlmProviderConfig(provider=LlmProviderType.OPENAI, model="gpt-4o-mini", api_key="test")
    provider = create_llm_provider(config)
    assert isinstance(provider, OpenAiProvider)


def test_create_null_provider():
    config = LlmProviderConfig(provider=LlmProviderType.NONE)
    provider = create_llm_provider(config)
    assert isinstance(provider, NullLlmProvider)


@pytest.mark.asyncio
async def test_null_provider_not_available():
    provider = NullLlmProvider()
    assert await provider.is_available() is False
