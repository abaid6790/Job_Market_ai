from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1/chat/completions"
    default_model = "llama-3.1-8b-instant"
    supports_embeddings = False  # Groq's API doesn't offer an embeddings endpoint
