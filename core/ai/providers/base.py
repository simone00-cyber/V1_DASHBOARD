from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProviderError(RuntimeError):
    """Base exception raised by AI providers."""


class AIProviderConfigurationError(AIProviderError):
    """Raised when the provider configuration is invalid."""


class AIProviderResponseError(AIProviderError):
    """Raised when the provider returns an invalid response."""


class AIProvider(ABC):
    """Interface implemented by every supported AI provider."""

    @abstractmethod
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """
        Generate one structured response.

        Providers must return a Python dictionary and must never
        expose provider-specific response objects to the application.
        """
        raise NotImplementedError