"""
Common interface every AI provider implements.

Routes and services never call a specific provider (GeminiProvider,
ClaudeProvider, etc.) directly — they go through AIProviderManager, which
only knows about this interface. Adding a new provider means implementing
this interface once, not touching any application logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class AIProviderError(Exception):
    """Raised when a provider call fails.

    `retryable` distinguishes transient failures (rate limit, timeout,
    5xx) — worth trying the next key or falling back to the next provider
    — from permanent ones (bad request, unsupported operation) where
    retrying the same call won't help but falling back to a *different*
    provider still might.
    """

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    vector: list[float]
    provider: str
    model: str
    raw: dict = field(default_factory=dict)


class AIProvider(ABC):
    """Every provider must implement generate, generate_json, and embed.
    `stream` has a default fallback (yield the full response as one
    chunk) for providers/call sites that don't need true token streaming."""

    name: str = "base"

    @abstractmethod
    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024, temperature: float = 0.7
    ) -> AIResponse:
        ...

    @abstractmethod
    def generate_json(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> AIResponse:
        ...

    @abstractmethod
    def embed(self, text: str) -> EmbeddingResponse:
        ...

    def stream(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024, temperature: float = 0.7):
        response = self.generate(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        yield response.text
