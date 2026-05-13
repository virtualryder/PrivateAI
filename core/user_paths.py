"""
Per-user path resolution for PrivateAI.

All user data lives under data/users/{user_id}/ so each account is fully
isolated at the filesystem level. The DATA_DIR env var lets Docker/Railway
override the root (e.g. /app/data → mounted on a persistent volume).

Note: relational data (user accounts, document metadata, audit log) is stored
in PostgreSQL (Railway) or SQLite (local dev) — see core/database.py.
Only binary data that cannot live in a relational DB (encryption keys,
vector store, uploaded files) lives on the filesystem here.
"""

import os
from pathlib import Path


_DATA_ROOT = Path(os.environ.get("DATA_DIR", "data"))


def get_user_dir(user_id: str) -> Path:
    """Root directory for a single user's private binary data."""
    return _DATA_ROOT / "users" / user_id


def get_key_path(user_id: str) -> Path:
    """Path to the user's Fernet encryption key file."""
    return get_user_dir(user_id) / ".key"


def get_vector_store_path(user_id: str) -> Path:
    """Path to the user's ChromaDB persistent vector store."""
    return get_user_dir(user_id) / "vector_store"


def get_settings_path(user_id: str) -> Path:
    """Path to the user's per-user settings YAML file."""
    return get_user_dir(user_id) / "settings.yaml"


def get_upload_dir(user_id: str) -> Path:
    """Staging directory for files being ingested (cleaned up after ingestion)."""
    return get_user_dir(user_id) / "uploads"


def get_user_storage_bytes(user_id: str) -> int:
    """Return total bytes used by a user's data directory."""
    user_dir = get_user_dir(user_id)
    if not user_dir.exists():
        return 0
    return sum(f.stat().st_size for f in user_dir.rglob("*") if f.is_file())
