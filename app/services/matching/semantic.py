"""
Semantic similarity via TF-IDF + cosine similarity.

This is a classical vector-space-model approach, not a deep embedding
model — appropriate here because Phase 7 (AI provider architecture)
doesn't exist yet, and the spec is explicit that NLP tasks should use the
cheapest suitable method rather than reaching for an LLM by default. If
Phase 7's AI provider abstraction is wired in later, this function's
signature (two texts in, a 0-100 score out) can be swapped for real
embeddings without touching any caller.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def semantic_similarity(text_a: str, text_b: str) -> float | None:
    """Returns a 0-100 similarity score, or None if either text is empty
    (there's nothing to compare — that's a data-availability gap, not a
    genuine 0% similarity)."""
    if not text_a or not text_a.strip() or not text_b or not text_b.strip():
        return None

    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([text_a, text_b])
    except ValueError:
        # Happens if, after stopword removal, there's no vocabulary left
        # (e.g. both texts are just numbers/punctuation).
        return None

    if matrix.shape[1] == 0:
        return None

    similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
    return round(float(similarity) * 100, 1)
