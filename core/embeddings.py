"""
Embedding provider abstraction.

Default: sentence-transformers all-MiniLM-L6-v2 (local, offline, no API cost).
Optional: OpenAI text-embedding-3-small (higher quality, but sends text to OpenAI).

The provider is selected via settings.yaml embedding_provider key.
Use @st.cache_resource on get_embedding_function() to avoid re-downloading weights.
"""

from __future__ import annotations

from typing import Callable


def get_local_embedding_function():
    """
    Returns a callable that embeds a list of texts using sentence-transformers.
    Downloads ~90MB of model weights on first call (cached in ~/.cache/huggingface/).
    Decorated with @st.cache_resource at the Streamlit call site to run only once per session.
    """
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(texts: list[str]) -> list[list[float]]:
        return model.encode(texts, convert_to_numpy=True).tolist()

    return embed


def get_openai_embedding_function(api_key: str):
    """
    Returns a callable that embeds texts using OpenAI text-embedding-3-small.
    WARNING: This sends text to OpenAI's servers. User must explicitly opt in.
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    def embed(texts: list[str]) -> list[list[float]]:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]

    return embed


def get_embedding_function(provider: str = "local", openai_api_key: str | None = None) -> Callable:
    """
    Factory: return the appropriate embedding function based on provider setting.

    provider: "local" | "openai"
    """
    if provider == "openai":
        if not openai_api_key:
            raise ValueError("OpenAI API key required for OpenAI embeddings")
        return get_openai_embedding_function(openai_api_key)
    return get_local_embedding_function()


def get_embedding_dimension(provider: str = "local") -> int:
    """Return the vector dimension for the chosen provider."""
    return 384 if provider == "local" else 1536
