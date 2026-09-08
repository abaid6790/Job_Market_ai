from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models import AIUsage, AICacheEntry
from app.services.ai.manager import AIProviderManager, NoProviderAvailableError
from app.services.ai.base import AIResponse, AIProviderError


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def _openai_success_payload(text="hi"):
    return {"model": "gpt-4o-mini", "choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def test_no_providers_configured_raises_clean_error(app):
    with app.app_context():
        manager = AIProviderManager({"AI_PROVIDER": "gemini", "AI_PROVIDER_ORDER": ["gemini"]})
        try:
            manager.generate("hello")
            assert False, "should have raised"
        except NoProviderAvailableError as exc:
            assert "no provider" in str(exc).lower()


def test_configured_providers_reflects_available_keys(app):
    with app.app_context():
        manager = AIProviderManager(
            {"AI_PROVIDER": "claude", "AI_PROVIDER_ORDER": [], "ANTHROPIC_API_KEY": "test-key"}
        )
        assert manager.configured_providers() == ["claude"]


def test_fallback_order_dedupes_and_skips_unconfigured(app):
    with app.app_context():
        manager = AIProviderManager(
            {
                "AI_PROVIDER": "claude",
                "AI_PROVIDER_ORDER": ["gemini", "claude", "openai"],  # gemini/openai not configured
                "ANTHROPIC_API_KEY": "test-key",
            }
        )
        assert manager._fallback_order() == ["claude"]


def test_generate_success_logs_usage(app):
    with app.app_context():
        manager = AIProviderManager(
            {"AI_PROVIDER": "openai", "AI_PROVIDER_ORDER": [], "OPENAI_API_KEY": "test-key"}
        )
        with patch("requests.post", return_value=_mock_response(200, _openai_success_payload("hello!"))):
            result = manager.generate("say hi", use_cache=False)

        assert result.text == "hello!"
        usage = AIUsage.query.order_by(AIUsage.id.desc()).first()
        assert usage.provider == "openai"
        assert usage.success is True
        assert usage.cache_hit is False


def test_fallback_to_second_provider_on_first_failure(app):
    with app.app_context():
        manager = AIProviderManager(
            {
                "AI_PROVIDER": "claude",
                "AI_PROVIDER_ORDER": ["claude", "openai"],
                "ANTHROPIC_API_KEY": "bad-claude-key",
                "OPENAI_API_KEY": "good-openai-key",
            }
        )

        def fake_post(url, headers=None, json=None, timeout=None):
            if "anthropic" in url:
                return _mock_response(401, text="unauthorized")
            return _mock_response(200, _openai_success_payload("fallback worked"))

        with patch("requests.post", side_effect=fake_post):
            result = manager.generate("hi", use_cache=False)

        assert result.text == "fallback worked"
        assert result.provider == "openai"

        # Both attempts should be logged: one failure, one success.
        usages = AIUsage.query.order_by(AIUsage.id).all()
        assert len(usages) == 2
        assert usages[0].provider == "claude"
        assert usages[0].success is False
        assert usages[1].provider == "openai"
        assert usages[1].success is True


def test_all_providers_fail_raises_with_combined_errors(app):
    with app.app_context():
        manager = AIProviderManager(
            {
                "AI_PROVIDER": "claude",
                "AI_PROVIDER_ORDER": ["claude", "openai"],
                "ANTHROPIC_API_KEY": "bad-key",
                "OPENAI_API_KEY": "also-bad-key",
            }
        )
        with patch("requests.post", return_value=_mock_response(401, text="unauthorized")):
            try:
                manager.generate("hi", use_cache=False)
                assert False, "should have raised"
            except NoProviderAvailableError as exc:
                assert "claude" in str(exc)
                assert "openai" in str(exc)

        # Two failures logged.
        assert AIUsage.query.filter_by(success=False).count() == 2


def test_cache_hit_avoids_network_call(app):
    with app.app_context():
        manager = AIProviderManager(
            {"AI_PROVIDER": "openai", "AI_PROVIDER_ORDER": [], "OPENAI_API_KEY": "test-key", "AI_CACHE_TTL_SECONDS": 3600}
        )

        with patch("requests.post", return_value=_mock_response(200, _openai_success_payload("cached answer"))) as mock_post:
            first = manager.generate("same prompt", use_cache=True)
            assert mock_post.call_count == 1

            second = manager.generate("same prompt", use_cache=True)
            # No additional HTTP call on the cache hit.
            assert mock_post.call_count == 1

        assert first.text == second.text == "cached answer"

        cache_hit_usage = AIUsage.query.filter_by(cache_hit=True).first()
        assert cache_hit_usage is not None
        assert AICacheEntry.query.count() == 1


def test_different_prompts_do_not_share_cache(app):
    with app.app_context():
        manager = AIProviderManager(
            {"AI_PROVIDER": "openai", "AI_PROVIDER_ORDER": [], "OPENAI_API_KEY": "test-key"}
        )

        def fake_post(url, headers=None, json=None, timeout=None):
            prompt = json["messages"][-1]["content"]
            return _mock_response(200, _openai_success_payload(f"response to {prompt}"))

        with patch("requests.post", side_effect=fake_post) as mock_post:
            r1 = manager.generate("prompt A", use_cache=True)
            r2 = manager.generate("prompt B", use_cache=True)

        assert mock_post.call_count == 2
        assert r1.text != r2.text


def test_use_cache_false_bypasses_cache(app):
    with app.app_context():
        manager = AIProviderManager(
            {"AI_PROVIDER": "openai", "AI_PROVIDER_ORDER": [], "OPENAI_API_KEY": "test-key"}
        )
        with patch("requests.post", return_value=_mock_response(200, _openai_success_payload("x"))) as mock_post:
            manager.generate("same", use_cache=False)
            manager.generate("same", use_cache=False)
        assert mock_post.call_count == 2


def test_embed_not_cached_even_when_use_cache_true(app):
    with app.app_context():
        manager = AIProviderManager(
            {"AI_PROVIDER": "openai", "AI_PROVIDER_ORDER": [], "OPENAI_API_KEY": "test-key"}
        )
        embed_payload = {"data": [{"embedding": [0.1, 0.2]}]}
        with patch("requests.post", return_value=_mock_response(200, embed_payload)) as mock_post:
            manager.embed("text", use_cache=True)
            manager.embed("text", use_cache=True)
        # embed() isn't in _CACHEABLE_METHODS, so both calls hit the network.
        assert mock_post.call_count == 2
