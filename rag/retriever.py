"""
ChromaDB retriever with on-the-fly decryption.

Privacy model:
  - ChromaDB stores vectors (not sensitive) + encrypted text in metadata["text_enc"]
  - We decrypt text_enc here, just before building the context string for the LLM
  - Decrypted text never persists to disk — it lives only in memory during the query

Each user has their own isolated ChromaDB at data/users/{user_id}/vector_store/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import chromadb
from cryptography.fernet import Fernet

from core.crypto import decrypt_text


_COLLECTION_NAME = "personal_docs"


def _get_collection(embedding_fn: Callable, vector_store_path: Path) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(vector_store_path))

    class _EmbedFn(chromadb.EmbeddingFunction):
        def __call__(self, input: list[str]) -> list[list[float]]:
            return embedding_fn(input)

    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_EmbedFn(),
        metadata={"hnsw:space": "cosine"},
    )


def retrieve_context(
    query: str,
    fernet: Fernet,
    embedding_fn: Callable,
    vector_store_path: Path,
    top_k: int = 5,
    enabled_doc_ids: list[str] | None = None,
) -> tuple[str, list[dict]]:
    """
    Retrieve the top-k most relevant chunks for a query from the user's vector store.

    Returns:
      context_str: formatted string of decrypted chunks for the prompt
      sources: list of dicts with filename, chunk_index, doc_id for citation
    """
    collection = _get_collection(embedding_fn, vector_store_path)

    # Build where filter: only retrieve from enabled documents
    where = None
    if enabled_doc_ids is not None:
        if len(enabled_doc_ids) == 0:
            return "", []
        elif len(enabled_doc_ids) == 1:
            where = {"doc_id": enabled_doc_ids[0]}
        else:
            where = {"doc_id": {"$in": enabled_doc_ids}}

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count() or 1),
            where=where,
            include=["metadatas", "distances"],
        )
    except Exception:
        return "", []

    if not results or not results["metadatas"] or not results["metadatas"][0]:
        return "", []

    context_parts = []
    sources = []

    for i, metadata in enumerate(results["metadatas"][0]):
        enc_text = metadata.get("text_enc", "")
        filename = metadata.get("filename", "unknown")
        chunk_idx = metadata.get("chunk_index", i)
        doc_id = metadata.get("doc_id", "")

        try:
            plain_text = decrypt_text(fernet, enc_text)
        except Exception:
            plain_text = "[decryption error]"

        context_parts.append(f"[Source: {filename}, chunk {chunk_idx}]\n{plain_text}")
        sources.append({"filename": filename, "chunk_index": chunk_idx, "doc_id": doc_id})

    return "\n\n---\n\n".join(context_parts), sources
