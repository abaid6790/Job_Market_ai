"""
AIProviderManager — the only thing the rest of the app should ever import
from app.services.ai. Routes and services call manager.generate(...) /
.generate_json(...) / .embed(...) and never touch a specific provider
class directly, so adding a 6th provider later never requires touching a
caller.

Fallback order: the configured default provider first, then
AI_PROVIDER_ORDER (de-duplicated), skipping any provider that has no API
key configured. Caching is checked once up front against the *primary*
provider's cache key (fast path, no network call at all on a hit); on a
miss, the manager tries providers in order and caches the result under
whichever provider/model actually served it.
"""
import time

from app.extensions import db
from app.services.ai.base import AIProviderError, AIResponse
from app.services.ai.cache import build_cache_key, get_cached, set_cached
from app.services.ai.usage import log_usage
from app.services.ai.providers.gemini import GeminiProvider
from app.services.ai.providers.groq import GroqProvider
from app.services.ai.providers.openrouter import OpenRouterProvider
from app.services.ai.providers.claude import ClaudeProvider
from app.services.ai.providers.openai import OpenAIProvider

_CACHEABLE_METHODS = {"generate", "generate_json"}


class NoProviderAvailableError(AIProviderError):
    def __init__(self, errors):
        message = "No AI provider is configured or all providers failed: " + "; ".join(errors)
        super().__init__(message, retryable=False)
        self.errors = errors


class AIProviderManager:
    def __init__(self, config: dict):
        self.config = config
        self.cache_ttl_seconds = config.get("AI_CACHE_TTL_SECONDS", 24 * 60 * 60)
        self.providers = self._build_providers(config)
        self.default = config.get("AI_PROVIDER", "gemini")
        self.order = config.get("AI_PROVIDER_ORDER", [])

    def _build_providers(self, config: dict) -> dict:
        providers = {}

        gemini_keys = config.get("GEMINI_API_KEYS", [])
        if gemini_keys:
            providers["gemini"] = GeminiProvider(
                gemini_keys, cooldown_seconds=config.get("AI_KEY_COOLDOWN_SECONDS", 60)
            )

        if config.get("GROQ_API_KEY"):
            providers["groq"] = GroqProvider(config["GROQ_API_KEY"])

        if config.get("OPENROUTER_API_KEY"):
            providers["openrouter"] = OpenRouterProvider(config["OPENROUTER_API_KEY"])

        if config.get("ANTHROPIC_API_KEY"):
            providers["claude"] = ClaudeProvider(config["ANTHROPIC_API_KEY"])

        if config.get("OPENAI_API_KEY"):
            providers["openai"] = OpenAIProvider(config["OPENAI_API_KEY"])

        return providers

    def configured_providers(self) -> list[str]:
        return list(self.providers.keys())

    def _fallback_order(self) -> list[str]:
        candidates = [self.default] + list(self.order)
        seen = set()
        result = []
        for name in candidates:
            if name in self.providers and name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def generate(self, prompt: str, *, user_id=None, use_cache=True, **kwargs) -> AIResponse:
        return self._call_with_fallback("generate", (prompt,), kwargs, user_id, use_cache)

    def generate_json(self, prompt: str, *, user_id=None, use_cache=True, **kwargs) -> AIResponse:
        return self._call_with_fallback("generate_json", (prompt,), kwargs, user_id, use_cache)

    def embed(self, text: str, *, user_id=None, use_cache=True, **kwargs):
        return self._call_with_fallback("embed", (text,), kwargs, user_id, use_cache)

    def _call_with_fallback(self, method_name: str, args: tuple, kwargs: dict, user_id, use_cache: bool):
        order = self._fallback_order()
        if not order:
            raise NoProviderAvailableError(["no provider has an API key configured"])

        prompt = args[0]

        if use_cache and method_name in _CACHEABLE_METHODS:
            primary_name = order[0]
            primary_provider = self.providers[primary_name]
            cache_key = build_cache_key(primary_name, primary_provider.model, method_name, prompt, kwargs)
            cached = get_cached(cache_key)
            if cached:
                log_usage(
                    provider=cached.provider,
                    model=cached.model,
                    method=method_name,
                    success=True,
                    cache_hit=True,
                    user_id=user_id,
                )
                return AIResponse(text=cached.response_text, provider=cached.provider, model=cached.model)

        errors = []
        for provider_name in order:
            provider = self.providers[provider_name]
            start = time.monotonic()
            try:
                method = getattr(provider, method_name)
                response = method(*args, **kwargs)
                elapsed_ms = round((time.monotonic() - start) * 1000)

                log_usage(
                    provider=provider_name,
                    model=getattr(response, "model", None),
                    method=method_name,
                    success=True,
                    prompt_tokens=getattr(response, "prompt_tokens", None),
                    completion_tokens=getattr(response, "completion_tokens", None),
                    total_tokens=getattr(response, "total_tokens", None),
                    response_time_ms=elapsed_ms,
                    user_id=user_id,
                )

                if use_cache and method_name in _CACHEABLE_METHODS:
                    cache_key = build_cache_key(provider_name, response.model, method_name, prompt, kwargs)
                    set_cached(
                        cache_key,
                        provider=provider_name,
                        model=response.model,
                        response_text=response.text,
                        meta={
                            "prompt_tokens": response.prompt_tokens,
                            "completion_tokens": response.completion_tokens,
                        },
                        ttl_seconds=self.cache_ttl_seconds,
                    )

                return response

            except AIProviderError as exc:
                elapsed_ms = round((time.monotonic() - start) * 1000)
                log_usage(
                    provider=provider_name,
                    method=method_name,
                    success=False,
                    response_time_ms=elapsed_ms,
                    user_id=user_id,
                    error_message=str(exc),
                )
                errors.append(f"{provider_name}: {exc}")
                continue

        raise NoProviderAvailableError(errors)
