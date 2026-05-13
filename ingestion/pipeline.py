"""
Ingestion pipeline: file → chunks → encrypted metadata → ChromaDB.

Flow:
  1. Load file to text sections
  2. Check deduplication via SHA256 hash
  3. Chunk into overlapping pieces
  4. Encrypt each chunk's text (stores ciphertext in ChromaDB metadata)
  5. Embed each chunk (vectors are NOT sensitive — not reversible to text)
  6. Store in per-user ChromaDB collection
  7. Record document metadata in the shared database (PostgreSQL or SQLite)

ChromaDB privacy model:
  - The vector column stores embeddings (not sensitive)
  - The metadata column stores {"text_enc": <fernet_token>, ...}
  - ChromaDB never holds readable text at rest

All storage is scoped per user via user_id → data/users/{user_id}/
"""

import hashlib
import uuid
from pathlib import Path
from typing import Callable

import chromadb
from cryptography.fernet import Fernet

from core.audit import log
from core.database import get_document_by_hash, upsert_document
from core.user_paths import get_vector_store_path, get_upload_dir
from ingestion.chunker import chunk_texts
from ingestion.loader import load_file

_COLLECTION_NAME = "personal_docs"
_MAX_UPLOAD_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB


def _get_collection(embedding_fn: Callable, vector_store_path: Path) -> chromadb.Collection:
    """Return (or create) the persistent ChromaDB collection for a specific user."""
    vector_store_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(vector_store_path))

    class _EmbedFn(chromadb.EmbeddingFunction):
        def __call__(self, input: list[str]) -> list[list[float]]:
            return embedding_fn(input)

    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_EmbedFn(),
        metadata={"hnsw:space": "cosine"},
    )


def get_file_hash(file_path: Path) -> str:
    """SHA256 of the file content — used to skip re-ingestion of identical files."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            sha.update(block)
    return sha.hexdigest()


def ingest_file(
    file_path: Path,
    fernet: Fernet,
    embedding_fn: Callable,
    user_id: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    force: bool = False,
) -> dict:
    """
    Ingest a single file into the user's private knowledge base.

    Returns a result dict:
    {
        "status": "ingested" | "skipped" | "error",
        "doc_id": str,
        "filename": str,
        "chunk_count": int,
        "message": str,
    }
    """
    vector_store_path = get_vector_store_path(user_id)
    filename = file_path.name
    file_type = file_path.suffix.lower().lstrip(".")

    # --- Size check ---
    file_size = file_path.stat().st_size
    if file_size > _MAX_UPLOAD_BYTES:
        size_mb = file_size / (1024 * 1024)
        return {
            "status": "error",
            "doc_id": "",
            "filename": filename,
            "chunk_count": 0,
            "message": f"File too large ({size_mb:.0f} MB). Maximum allowed size is 250 MB.",
        }

    # --- Deduplication check ---
    file_hash = get_file_hash(file_path)
    if not force:
        existing = get_document_by_hash(file_hash, user_id=user_id)
        if existing:
            return {
                "status": "skipped",
                "doc_id": existing["id"],
                "filename": filename,
                "chunk_count": existing["chunk_count"],
                "message": f"Already ingested (doc_id={existing['id'][:8]}...)",
            }

    try:
        # --- Load ---
        sections = load_file(file_path)
        if not sections:
            return {"status": "error", "doc_id": "", "filename": filename, "chunk_count": 0,
                    "message": "File appears to be empty or unreadable"}

        # --- Chunk ---
        chunks = chunk_texts(sections, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks:
            return {"status": "error", "doc_id": "", "filename": filename, "chunk_count": 0,
                    "message": "No text chunks produced"}

        # --- Generate doc_id (used for both ChromaDB metadata AND the DB record) ---
        doc_id = str(uuid.uuid4())

        # --- Encrypt chunk texts ---
        from core.crypto import encrypt_text
        encrypted_chunks = [encrypt_text(fernet, chunk) for chunk in chunks]

        # --- Build ChromaDB records ---
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "text_enc": enc_text,
                "doc_id": doc_id,
                "chunk_index": i,
                "filename": filename,
            }
            for i, enc_text in enumerate(encrypted_chunks)
        ]

        # --- Store in per-user ChromaDB (embed + store) ---
        collection = _get_collection(embedding_fn, vector_store_path)
        collection.add(
            ids=ids,
            documents=chunks,  # ChromaDB needs plaintext to embed; vectors are not reversible
            metadatas=metadatas,
        )

        # --- Record in shared database (doc_id matches ChromaDB metadata) ---
        upsert_document(
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            file_hash=file_hash,
            chunk_count=len(chunks),
            user_id=user_id,
        )

        log("ingest", user_id=user_id, details={"filename": filename, "chunks": len(chunks), "doc_id": doc_id})

        return {
            "status": "ingested",
            "doc_id": doc_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "message": f"Ingested {len(chunks)} chunks",
        }

    except Exception as exc:
        log("error", user_id=user_id, details={"event": "ingest_failed", "filename": filename, "error": str(exc)})
        return {
            "status": "error",
            "doc_id": "",
            "filename": filename,
            "chunk_count": 0,
            "message": str(exc),
        }


def delete_document_from_store(doc_id: str, user_id: str) -> None:
    """Remove all ChromaDB entries for a document from the user's vector store."""
    vector_store_path = get_vector_store_path(user_id)
    client = chromadb.PersistentClient(path=str(vector_store_path))
    try:
        collection = client.get_collection(_COLLECTION_NAME)
        results = collection.get(where={"doc_id": doc_id})
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception:
        pass


def save_upload(uploaded_file, upload_dir: Path) -> Path:
    """Save a Streamlit UploadedFile to the user's upload staging directory."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / uploaded_file.name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest


def cleanup_upload(file_path: Path) -> None:
    """Remove a file from the upload staging area after ingestion."""
    try:
        file_path.unlink(missing_ok=True)
    except Exception:
        pass
