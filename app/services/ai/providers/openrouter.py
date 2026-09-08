from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"
    base_url = "https://openrouter.ai/api/v1/chat/completions"
    default_model = "meta-llama/llama-3.1-8b-instruct:free"
    supports_embeddings = False  # OpenRouter proxies chat completions, not a dedicated embeddings API

    def _headers(self):
        headers = super()._headers()
        # OpenRouter recommends these but doesn't require them; harmless to include.
        headers["HTTP-Referer"] = "https://jobmarket-ai.local"
        headers["X-Title"] = "JobMarket AI"
        return headers
