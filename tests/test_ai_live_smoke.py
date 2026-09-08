"""
A genuinely real (non-mocked) network test against api.anthropic.com.

This sandbox has no configured ANTHROPIC_API_KEY, and of the five AI
provider domains this app talks to, only api.anthropic.com is reachable
through the network egress rules here — generativelanguage.googleapis.com
(Gemini), api.groq.com, openrouter.ai, and api.openai.com are not. So this
is the only provider that can be verified against a real endpoint at all
in this environment.

Without a real key, we can't verify a *successful* generation end-to-end
here — that requires a real deployment with real credentials. What this
test DOES prove, against the real API rather than a mock: our request
actually reaches Anthropic's servers, and our error-handling code
correctly classifies a real 401 Unauthorized response (not a
hand-crafted mock) as a non-retryable AIProviderError. That's a
meaningful signal that the HTTP plumbing itself is genuinely correct, not
just internally self-consistent with our own mocks.

Skipped automatically if the network is unreachable (e.g. running in a
fully offline environment), so it doesn't break unrelated CI runs.
"""
import socket

import pytest

from app.services.ai.providers.claude import ClaudeProvider
from app.services.ai.base import AIProviderError


def _network_reachable() -> bool:
    try:
        socket.create_connection(("api.anthropic.com", 443), timeout=5)
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _network_reachable(), reason="api.anthropic.com not reachable from this environment")
def test_claude_provider_reaches_real_api_and_handles_real_401():
    provider = ClaudeProvider(api_key="sk-ant-invalid-test-key-no-real-credentials")

    with pytest.raises(AIProviderError) as exc_info:
        provider.generate("This should fail with a real 401 from the real API.")

    # A real, live 401 from Anthropic's actual server — not a mock.
    assert exc_info.value.retryable is False
    assert "authentication" in str(exc_info.value).lower()
