"""
Shared implementation for providers using the OpenAI-compatible chat
completions API shape (OpenAI itself, Groq, OpenRouter). Subclasses only
need to set base_url, default model, and any extra headers — the request
construction, error classification, and response parsing are identical
across all three.
"""
import requests

from app.services.ai.base import AIProvider, AIProviderError, AIResponse, EmbeddingResponse
from app.services.ai.json_utils import parse_json_response


class OpenAICompatibleProvider(AIProvider):
    base_url = ""
    embeddings_url = None
    default_model = ""
    default_embedding_model = None
    supports_embeddings = True

    def __init__(self, api_key, model=None, timeout=30):
        self.api_key = api_key
        self.model = model or self.default_model
        self.timeout = timeout

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _post(self, url, payload):
        try:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise AIProviderError(f"{self.name} request timed out: {exc}", retryable=True) from exc
        except requests.exceptions.RequestException as exc:
            raise AIProviderError(f"{self.name} request failed: {exc}", retryable=True) from exc

        if resp.status_code == 401:
            raise AIProviderError(f"{self.name} authentication failed (check API key).", retryable=False)
        if resp.status_code == 429:
            raise AIProviderError(f"{self.name} rate limit exceeded.", retryable=True)
        if resp.status_code >= 500:
            raise AIProviderError(f"{self.name} server error ({resp.status_code}).", retryable=True)
        if resp.status_code >= 400:
            raise AIProviderError(
                f"{self.name} request error ({resp.status_code}): {resp.text[:300]}", retryable=False
            )

        try:
            return resp.json()
        except ValueError as exc:
            raise AIProviderError(f"{self.name} returned invalid JSON: {exc}", retryable=True) from exc

    def _chat(self, prompt, system, max_tokens, temperature):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = self._post(self.base_url, payload)

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"Unexpected {self.name} response shape: {exc}", retryable=True) from exc

        usage = data.get("usage", {})
        return AIResponse(
            text=text,
            provider=self.name,
            model=data.get("model", self.model),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            raw=data,
        )

    def generate(self, prompt, *, system=None, max_tokens=1024, temperature=0.7):
        return self._chat(prompt, system, max_tokens, temperature)

    def generate_json(self, prompt, *, system=None, max_tokens=1024):
        json_instruction = (
            "Respond with ONLY valid JSON. No markdown code fences, no preamble, no explanation."
        )
        combined_system = f"{system}\n\n{json_instruction}" if system else json_instruction
        response = self._chat(prompt, combined_system, max_tokens, temperature=0.0)
        parse_json_response(response.text)
        return response

    def embed(self, text):
        if not self.supports_embeddings or not self.embeddings_url:
            raise AIProviderError(f"{self.name} does not support embeddings.", retryable=False)

        model = self.default_embedding_model
        payload = {"model": model, "input": text}
        data = self._post(self.embeddings_url, payload)

        try:
            vector = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"Unexpected {self.name} embedding response shape: {exc}", retryable=True) from exc

        return EmbeddingResponse(vector=vector, provider=self.name, model=model, raw=data)
