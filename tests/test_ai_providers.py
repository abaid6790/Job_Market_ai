"""
Provider tests using mocked HTTP responses.

These mock `requests.post` with response payloads shaped exactly like
each provider's real documented API — this verifies our request
construction and response parsing are correct without needing real API
keys or live network access (only api.anthropic.com is reachable from
this environment, and even that has no test credentials available — see
test_ai_live_smoke.py for what *is* verified against the real endpoint).
"""
from unittest.mock import patch, MagicMock

import pytest

from app.services.ai.base import AIProviderError
from app.services.ai.providers.claude import ClaudeProvider
from app.services.ai.providers.openai import OpenAIProvider
from app.services.ai.providers.groq import GroqProvider
from app.services.ai.providers.openrouter import OpenRouterProvider
from app.services.ai.providers.gemini import GeminiProvider


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


# --- Claude ---

def test_claude_generate_parses_real_response_shape():
    provider = ClaudeProvider(api_key="test-key")
    fake_response = {
        "id": "msg_123",
        "model": "claude-3-5-haiku-20241022",
        "content": [{"type": "text", "text": "Hello from Claude"}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    with patch("requests.post", return_value=_mock_response(200, fake_response)) as mock_post:
        result = provider.generate("Say hello")

    assert result.text == "Hello from Claude"
    assert result.provider == "claude"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.total_tokens == 15

    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["x-api-key"] == "test-key"
    assert call_kwargs["json"]["messages"][0]["content"] == "Say hello"


def test_claude_401_raises_non_retryable():
    provider = ClaudeProvider(api_key="bad-key")
    with patch("requests.post", return_value=_mock_response(401, text="unauthorized")):
        with pytest.raises(AIProviderError) as exc_info:
            provider.generate("hi")
    assert exc_info.value.retryable is False


def test_claude_429_raises_retryable():
    provider = ClaudeProvider(api_key="test-key")
    with patch("requests.post", return_value=_mock_response(429, text="rate limited")):
        with pytest.raises(AIProviderError) as exc_info:
            provider.generate("hi")
    assert exc_info.value.retryable is True


def test_claude_embed_not_supported():
    provider = ClaudeProvider(api_key="test-key")
    with pytest.raises(AIProviderError) as exc_info:
        provider.embed("some text")
    assert exc_info.value.retryable is False


def test_claude_generate_json_parses_valid_json():
    provider = ClaudeProvider(api_key="test-key")
    fake_response = {
        "model": "claude-3-5-haiku-20241022",
        "content": [{"type": "text", "text": '{"skills": ["Python", "Docker"]}'}],
        "usage": {"input_tokens": 20, "output_tokens": 10},
    }
    with patch("requests.post", return_value=_mock_response(200, fake_response)):
        result = provider.generate_json("Extract skills")
    assert '"skills"' in result.text


def test_claude_generate_json_rejects_invalid_json():
    provider = ClaudeProvider(api_key="test-key")
    fake_response = {
        "model": "claude-3-5-haiku-20241022",
        "content": [{"type": "text", "text": "not valid json at all"}],
        "usage": {"input_tokens": 5, "output_tokens": 5},
    }
    with patch("requests.post", return_value=_mock_response(200, fake_response)):
        with pytest.raises(ValueError):
            provider.generate_json("Extract skills")


# --- OpenAI-compatible (OpenAI, Groq, OpenRouter share the same base) ---

def test_openai_generate_parses_real_response_shape():
    provider = OpenAIProvider(api_key="test-key")
    fake_response = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"role": "assistant", "content": "Hi there"}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11},
    }
    with patch("requests.post", return_value=_mock_response(200, fake_response)) as mock_post:
        result = provider.generate("hello")

    assert result.text == "Hi there"
    assert result.total_tokens == 11
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_openai_embed_parses_real_response_shape():
    provider = OpenAIProvider(api_key="test-key")
    fake_response = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
    with patch("requests.post", return_value=_mock_response(200, fake_response)) as mock_post:
        result = provider.embed("some text")

    assert result.vector == [0.1, 0.2, 0.3]
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["input"] == "some text"


def test_groq_does_not_support_embeddings():
    provider = GroqProvider(api_key="test-key")
    with pytest.raises(AIProviderError) as exc_info:
        provider.embed("text")
    assert exc_info.value.retryable is False


def test_openrouter_includes_recommended_headers():
    provider = OpenRouterProvider(api_key="test-key")
    fake_response = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "choices": [{"message": {"content": "response"}}],
        "usage": {},
    }
    with patch("requests.post", return_value=_mock_response(200, fake_response)) as mock_post:
        provider.generate("hi")
    headers = mock_post.call_args.kwargs["headers"]
    assert "HTTP-Referer" in headers
    assert "X-Title" in headers


def test_500_error_is_retryable():
    provider = OpenAIProvider(api_key="test-key")
    with patch("requests.post", return_value=_mock_response(500, text="server error")):
        with pytest.raises(AIProviderError) as exc_info:
            provider.generate("hi")
    assert exc_info.value.retryable is True


def test_malformed_response_shape_raises_gracefully():
    provider = OpenAIProvider(api_key="test-key")
    with patch("requests.post", return_value=_mock_response(200, {"unexpected": "shape"})):
        with pytest.raises(AIProviderError):
            provider.generate("hi")


# --- Gemini (multi-key rotation) ---

def test_gemini_generate_parses_real_response_shape():
    provider = GeminiProvider(api_keys=["key1"])
    fake_response = {
        "candidates": [{"content": {"parts": [{"text": "Gemini says hi"}]}}],
        "usageMetadata": {"promptTokenCount": 6, "candidatesTokenCount": 4, "totalTokenCount": 10},
    }
    with patch("requests.post", return_value=_mock_response(200, fake_response)) as mock_post:
        result = provider.generate("hello")

    assert result.text == "Gemini says hi"
    assert result.total_tokens == 10
    url = mock_post.call_args.args[0]
    assert "key=key1" in url


def test_gemini_rotates_to_next_key_on_429():
    provider = GeminiProvider(api_keys=["key1", "key2"])
    fake_success = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
        "usageMetadata": {},
    }

    call_urls = []

    def fake_post(url, json=None, timeout=None):
        call_urls.append(url)
        if "key=key1" in url:
            return _mock_response(429, text="rate limited")
        return _mock_response(200, fake_success)

    with patch("requests.post", side_effect=fake_post):
        result = provider.generate("hello")

    assert result.text == "ok"
    assert len(call_urls) == 2
    assert "key=key1" in call_urls[0]
    assert "key=key2" in call_urls[1]


def test_gemini_all_keys_exhausted_raises():
    provider = GeminiProvider(api_keys=["key1", "key2"])
    with patch("requests.post", return_value=_mock_response(429, text="rate limited")):
        with pytest.raises(AIProviderError) as exc_info:
            provider.generate("hello")
    assert exc_info.value.retryable is True


def test_gemini_no_keys_configured_raises_immediately():
    provider = GeminiProvider(api_keys=[])
    with pytest.raises(AIProviderError) as exc_info:
        provider.generate("hello")
    assert exc_info.value.retryable is False


def test_gemini_safety_blocked_response_raises_non_retryable():
    provider = GeminiProvider(api_keys=["key1"])
    with patch("requests.post", return_value=_mock_response(200, {"candidates": []})):
        with pytest.raises(AIProviderError) as exc_info:
            provider.generate("hello")
    assert exc_info.value.retryable is False


def test_gemini_embed_parses_real_response_shape():
    provider = GeminiProvider(api_keys=["key1"])
    fake_response = {"embedding": {"values": [0.5, 0.6]}}
    with patch("requests.post", return_value=_mock_response(200, fake_response)):
        result = provider.embed("text")
    assert result.vector == [0.5, 0.6]
