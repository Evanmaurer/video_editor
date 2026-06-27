from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from montage_backend.logging import get_logger
from montage_backend.models.domain import AiFeatureStatus, LlmProviderConfig, LlmProviderType

logger = get_logger(__name__)


class LlmProvider(ABC):
    @abstractmethod
    async def is_available(self) -> bool: ...

    @abstractmethod
    async def complete(self, messages: list[dict[str, str]]) -> str: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...


class OllamaProvider(LlmProvider):
    def __init__(self, config: LlmProviderConfig) -> None:
        self._config = config
        self._base_url = (config.base_url or "http://127.0.0.1:11434").rstrip("/")

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def complete(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("message", {}).get("content", ""))


class OpenAiProvider(LlmProvider):
    def __init__(self, config: LlmProviderConfig) -> None:
        self._config = config
        self._base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")

    @property
    def provider_name(self) -> str:
        return "openai"

    async def is_available(self) -> bool:
        return bool(self._config.api_key)

    async def complete(self, messages: list[dict[str, str]]) -> str:
        if not self._config.api_key:
            raise RuntimeError("OpenAI API key not configured")
        headers = {"Authorization": f"Bearer {self._config.api_key}"}
        payload = {"model": self._config.model, "messages": messages}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])


class NullLlmProvider(LlmProvider):
    @property
    def provider_name(self) -> str:
        return "none"

    async def is_available(self) -> bool:
        return False

    async def complete(self, messages: list[dict[str, str]]) -> str:
        raise RuntimeError("LLM provider is disabled")


def create_llm_provider(config: LlmProviderConfig) -> LlmProvider:
    if config.provider == LlmProviderType.OLLAMA:
        return OllamaProvider(config)
    if config.provider == LlmProviderType.OPENAI:
        return OpenAiProvider(config)
    return NullLlmProvider()


class LlmService:
    """Provider abstraction for AI chat. Rest of app does not depend on specific LLM."""

    def __init__(self) -> None:
        self._provider: LlmProvider = NullLlmProvider()
        self._config: LlmProviderConfig | None = None

    async def configure(self, config: LlmProviderConfig) -> AiFeatureStatus:
        self._config = config
        self._provider = create_llm_provider(config)
        available = await self._provider.is_available()
        if available:
            logger.info("llm_configured", provider=config.provider.value, model=config.model)
            return AiFeatureStatus(
                chat_enabled=True,
                chat_disabled_reason=None,
            )
        reason = self._disabled_reason(config)
        logger.warning("llm_unavailable", provider=config.provider.value, reason=reason)
        return AiFeatureStatus(
            chat_enabled=False,
            chat_disabled_reason=reason,
        )

    def _disabled_reason(self, config: LlmProviderConfig) -> str:
        if config.provider == LlmProviderType.NONE:
            return "AI chat is disabled. Manual editing remains fully available."
        if config.provider == LlmProviderType.OLLAMA:
            return (
                "Ollama is not running or the selected model is unavailable. "
                "Start Ollama or change the model in Settings."
            )
        return "Cloud LLM is not configured. Add an API key in Settings."

    async def get_status(self) -> AiFeatureStatus:
        if self._config is None:
            return AiFeatureStatus(
                chat_enabled=False,
                chat_disabled_reason="LLM provider not configured",
            )
        if await self._provider.is_available():
            return AiFeatureStatus(chat_enabled=True, chat_disabled_reason=None)
        return AiFeatureStatus(
            chat_enabled=False,
            chat_disabled_reason=self._disabled_reason(self._config),
        )

    async def complete(self, messages: list[dict[str, str]]) -> str | None:
        try:
            if not await self._provider.is_available():
                return None
            return await self._provider.complete(messages)
        except Exception as exc:
            logger.error("llm_complete_failed", error=str(exc))
            return None


llm_service = LlmService()
