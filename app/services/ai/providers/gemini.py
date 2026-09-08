"""
Google Gemini provider (generativelanguage.googleapis.com).

The only provider with multi-key rotation, per the spec: when a key hits
a rate limit or quota error, it's put in cooldown and the next available
key is tried automatically, within the same provider — this happens
*before* AIProviderManager would ever consider falling back to a
different provider entirely.
"""
import requests

from app.services.ai.base import AIProvider, AIProviderError, AIResponse, EmbeddingResponse
from app.services.ai.json_utils import parse_json_response
from app.services.ai.key_rotation import KeyRotator

DEFAULT_MODEL = "gemini-1.5-flash"
DEFAULT_EMBEDDING_MODEL = "text-embedding-004"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_keys, model=DEFAULT_MODEL, timeout=30, cooldown_seconds=60):
        self.rotator = KeyRotator(api_keys, cooldown_seconds=cooldown_seconds)
        self.model = model
        self.timeout = timeout

    def _request_with_rotation(self, url_suffix, payload):
        if not self.rotator.has_keys():
            raise AIProviderError("No Gemini API keys configured.", retryable=False)

        attempts = len(self.rotator.available_keys()) or 1
        last_error = None

        for _ in range(attempts):
            key = self.rotator.get_key()
            if key is None:
                raise AIProviderError("All Gemini API keys are in cooldown.", retryable=True)

            url = f"{BASE_URL}/{url_suffix}?key={key}"
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
            except requests.exceptions.Timeout as exc:
                last_error = AIProviderError(f"Gemini request timed out: {exc}", retryable=True)
                continue
            except requests.exceptions.RequestException as exc:
                last_error = AIProviderError(f"Gemini request failed: {exc}", retryable=True)
                continue

            if resp.status_code in (429, 403):
                self.rotator.mark_failure(key)
                last_error = AIProviderError(f"Gemini key rate-limited ({resp.status_code}).", retryable=True)
                continue

            if resp.status_code == 401:
                self.rotator.mark_failure(key)
                last_error = AIProviderError("Gemini authentication failed for this key.", retryable=False)
                continue

            if resp.status_code >= 500:
                raise AIProviderError(f"Gemini server error ({resp.status_code}).", retryable=True)

            if resp.status_code >= 400:
                raise AIProviderError(
                    f"Gemini request error ({resp.status_code}): {resp.text[:300]}", retryable=False
                )

            self.rotator.mark_success(key)
            try:
                return resp.json()
            except ValueError as exc:
                raise AIProviderError(f"Gemini returned invalid JSON: {exc}", retryable=True) from exc

        raise last_error or AIProviderError("All Gemini keys failed.", retryable=True)

    def _generate(self, prompt, system, max_tokens, temperature):
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        data = self._request_with_rotation(f"{self.model}:generateContent", payload)

        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIProviderError(
                    "Gemini returned no candidates (possibly blocked by safety filters).", retryable=False
                )
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, TypeError) as exc:
            raise AIProviderError(f"Unexpected Gemini response shape: {exc}", retryable=True) from exc

        usage = data.get("usageMetadata", {})
        return AIResponse(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"),
            total_tokens=usage.get("totalTokenCount"),
            raw=data,
        )

    def generate(self, prompt, *, system=None, max_tokens=1024, temperature=0.7):
        return self._generate(prompt, system, max_tokens, temperature)

    def generate_json(self, prompt, *, system=None, max_tokens=1024):
        json_instruction = (
            "Respond with ONLY valid JSON. No markdown code fences, no preamble, no explanation."
        )
        combined_system = f"{system}\n\n{json_instruction}" if system else json_instruction
        response = self._generate(prompt, combined_system, max_tokens, temperature=0.0)
        parse_json_response(response.text)
        return response

    def embed(self, text):
        payload = {"content": {"parts": [{"text": text}]}}
        data = self._request_with_rotation(f"{DEFAULT_EMBEDDING_MODEL}:embedContent", payload)

        try:
            vector = data["embedding"]["values"]
        except (KeyError, TypeError) as exc:
            raise AIProviderError(f"Unexpected Gemini embedding response shape: {exc}", retryable=True) from exc

        return EmbeddingResponse(vector=vector, provider=self.name, model=DEFAULT_EMBEDDING_MODEL, raw=data)
