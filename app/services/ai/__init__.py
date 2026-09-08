"""AI provider architecture package.

Use `get_ai_manager()` to access the shared AIProviderManager instance —
never import a specific provider class outside of `app/services/ai/`.
"""
from flask import current_app


def get_ai_manager():
    return current_app.extensions["ai_manager"]