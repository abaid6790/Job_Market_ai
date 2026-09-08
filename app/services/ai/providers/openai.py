from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1/chat/completions"
    embeddings_url = "https://api.openai.com/v1/embeddings"
    default_model = "gpt-4o-mini"
    default_embedding_model = "text-embedding-3-small"
    supports_embeddings = True
