"""
Anthropic Claude provider (api.anthropic.com/v1/messages).

Anthropic doesn't offer a public text-embeddings endpoint, so embed()
raises AIProviderError(retryable=False) — the manager's fallback logic
treats this exactly like any other provider failure and moves on to the
next configured provider, which is the correct behavior here rather than
a special case.
"""
import requests

from app.services.ai.base import AIProvider, AIProviderError, AIResponse, EmbeddingResponse
from app.services.ai.json_utils import parse_json_response

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-3-5-haiku-20241022"


class ClaudeProvider(AIProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def _post(self, payload: dict) -> dict:
        try:
            resp = requests.post(API_URL, headers=self._headers(), json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise AIProviderError(f"Claude request timed out: {exc}", retryable=True) from exc
        except requests.exceptions.RequestException as exc:
            raise AIProviderError(f"Claude request failed: {exc}", retryable=True) from exc

        if resp.status_code == 401:
            raise AIProviderError("Claude authentication failed (check ANTHROPIC_API_KEY).", retryable=False)
        if resp.status_code == 429:
            raise AIProviderError("Claude rate limit exceeded.", retryable=True)
        if resp.status_code >= 500:
            raise AIProviderError(f"Claude server error ({resp.status_code}).", retryable=True)
        if resp.status_code >= 400:
            raise AIProviderError(f"Claude request error ({resp.status_code}): {resp.text[:300]}", retryable=False)

        try:
            return resp.json()
        except ValueError as exc:
            raise AIProviderError(f"Claude returned invalid JSON: {exc}", retryable=True) from exc

    def _generate(self, prompt: str, system, max_tokens: int, temperature: float) -> AIResponse:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        data = self._post(payload)

        try:
            text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise AIProviderError(f"Unexpected Claude response shape: {exc}", retryable=True) from exc

        usage = data.get("usage", {})
        return AIResponse(
            text=text,
            provider=self.name,
            model=data.get("model", self.model),
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
            total_tokens=(usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0) or None,
            raw=data,
        )

    def generate(self, prompt, *, system=None, max_tokens=1024, temperature=0.7) -> AIResponse:
        return self._generate(prompt, system, max_tokens, temperature)

    def generate_json(self, prompt, *, system=None, max_tokens=1024) -> AIResponse:
        json_instruction = (
            "Respond with ONLY valid JSON. No markdown code fences, no preamble, no explanation."
        )
        combined_system = f"{system}\n\n{json_instruction}" if system else json_instruction
        response = self._generate(prompt, combined_system, max_tokens, temperature=0.0)
        parse_json_response(response.text)  # raises ValueError if invalid — caller decides how to handle
        return response

    def embed(self, text: str) -> EmbeddingResponse:
        raise AIProviderError("Claude does not provide a text embeddings API.", retryable=False)
