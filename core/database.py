"""
Database layer for PrivateAI.

Backends:
  - PostgreSQL when DATABASE_URL env var is set (Railway, production)
  - SQLite for local development (no DATABASE_URL required)

All tables include a user_id column for multi-tenant isolation.
Call init_db() once at startup — it creates all tables including users.
"""

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_DATABASE_URL = os.environ.get("DATABASE_URL")
_USE_PG = bool(_DATABASE_URL)
_DATA_ROOT = Path(os.environ.get("DATA_DIR", "data"))


def _ph() -> str:
    """SQL placeholder: %s for Postgres, ? for SQLite."""
    return "%s" if _USE_PG else "?"


@contextmanager
def _cursor():
    """Yield a database cursor; commit on success, rollback on error."""
    if _USE_PG:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(_DATABASE_URL, cursor_factory=RealDictCursor)
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        import sqlite3

        db_path = _DATA_ROOT / "app.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool_val(b: bool):
    """Normalize bool for the active backend."""
    return b if _USE_PG else (1 if b else 0)


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    if _USE_PG:
        stmts = [
            """CREATE TABLE IF NOT EXISTS users (
                id            VARCHAR(36) PRIMARY KEY,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin      BOOLEAN DEFAULT FALSE,
                created_at    TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS documents (
                id          VARCHAR(36) PRIMARY KEY,
                user_id     VARCHAR(36) NOT NULL,
                filename    TEXT NOT NULL,
                file_type   TEXT NOT NULL,
                file_hash   TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                ingested_at TEXT NOT NULL,
                enabled     BOOLEAN DEFAULT TRUE
            )""",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_user_hash ON documents(user_id, file_hash)",
            """CREATE TABLE IF NOT EXISTS audit_log (
                id          SERIAL PRIMARY KEY,
                user_id     VARCHAR(36) NOT NULL,
                timestamp   TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                details     TEXT,
                model_used  TEXT,
                local_only  BOOLEAN DEFAULT TRUE
            )""",
            """CREATE TABLE IF NOT EXISTS settings (
                user_id     VARCHAR(36) NOT NULL,
                key         TEXT NOT NULL,
                value       TEXT NOT NULL,
                PRIMARY KEY (user_id, key)
            )""",
        ]
    else:
        stmts = [
            """CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin      INTEGER DEFAULT 0,
                created_at    TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS documents (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                filename    TEXT NOT NULL,
                file_type   TEXT NOT NULL,
                file_hash   TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                ingested_at TEXT NOT NULL,
                enabled     INTEGER DEFAULT 1
            )""",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_user_hash ON documents(user_id, file_hash)",
            """CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                details     TEXT,
                model_used  TEXT,
                local_only  INTEGER DEFAULT 1
            )""",
            """CREATE TABLE IF NOT EXISTS settings (
                user_id     TEXT NOT NULL,
                key         TEXT NOT NULL,
                value       TEXT NOT NULL,
                PRIMARY KEY (user_id, key)
            )""",
        ]

    with _cursor() as cur:
        for stmt in stmts:
            cur.execute(stmt)


# ── Documents ─────────────────────────────────────────────────────────────────

def upsert_document(
    doc_id: str,
    filename: str,
    file_type: str,
    file_hash: str,
    chunk_count: int,
    user_id: str,
) -> str:
    """
    Insert or update a document record. Returns doc_id.
    If user_id+file_hash already exists, updates chunk_count and re-enables the document.
    """
    ph = _ph()
    with _cursor() as cur:
        cur.execute(
            f"SELECT id FROM documents WHERE user_id={ph} AND file_hash={ph}",
            (user_id, file_hash),
        )
        existing = cur.fetchone()
        if existing:
            doc_id = existing["id"]
            cur.execute(
                f"UPDATE documents SET chunk_count={ph}, ingested_at={ph}, enabled={ph} WHERE id={ph}",
                (chunk_count, _now(), _bool_val(True), doc_id),
            )
        else:
            cur.execute(
                f"""INSERT INTO documents (id, user_id, filename, file_type, file_hash, chunk_count, ingested_at, enabled)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                (doc_id, user_id, filename, file_type, file_hash, chunk_count, _now(), _bool_val(True)),
            )
    return doc_id


def list_documents(user_id: str) -> list[dict]:
    ph = _ph()
    with _cursor() as cur:
        cur.execute(
            f"SELECT * FROM documents WHERE user_id={ph} ORDER BY ingested_at DESC",
            (user_id,),
        )
        return _rows(cur)


def get_document_by_hash(file_hash: str, user_id: str) -> dict | None:
    ph = _ph()
    with _cursor() as cur:
        cur.execute(
            f"SELECT * FROM documents WHERE user_id={ph} AND file_hash={ph}",
            (user_id, file_hash),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def set_document_enabled(doc_id: str, enabled: bool, user_id: str) -> None:
    ph = _ph()
    with _cursor() as cur:
        cur.execute(
            f"UPDATE documents SET enabled={ph} WHERE id={ph} AND user_id={ph}",
            (_bool_val(enabled), doc_id, user_id),
        )


def delete_document(doc_id: str, user_id: str) -> None:
    ph = _ph()
    with _cursor() as cur:
        cur.execute(
            f"DELETE FROM documents WHERE id={ph} AND user_id={ph}",
            (doc_id, user_id),
        )


# ── Audit log ─────────────────────────────────────────────────────────────────

def add_audit_event(
    event_type: str,
    user_id: str,
    details: dict | None = None,
    model_used: str | None = None,
    local_only: bool = True,
) -> None:
    ph = _ph()
    with _cursor() as cur:
        cur.execute(
            f"""INSERT INTO audit_log (user_id, timestamp, event_type, details, model_used, local_only)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
            (user_id, _now(), event_type, json.dumps(details) if details else None, model_used, _bool_val(local_only)),
        )


def get_audit_log(user_id: str, limit: int = 200) -> list[dict]:
    ph = _ph()
    with _cursor() as cur:
        cur.execute(
            f"SELECT * FROM audit_log WHERE user_id={ph} ORDER BY id DESC LIMIT {ph}",
            (user_id, limit),
        )
        return _rows(cur)


# ── Settings (DB-backed, complements per-user YAML) ───────────────────────────

def get_setting(key: str, user_id: str, default: str | None = None) -> str | None:
    ph = _ph()
    with _cursor() as cur:
        cur.execute(
            f"SELECT value FROM settings WHERE user_id={ph} AND key={ph}",
            (user_id, key),
        )
        row = cur.fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str, user_id: str) -> None:
    ph = _ph()
    if _USE_PG:
        sql = f"INSERT INTO settings (user_id, key, value) VALUES ({ph}, {ph}, {ph}) ON CONFLICT(user_id, key) DO UPDATE SET value=EXCLUDED.value"
    else:
        sql = f"INSERT INTO settings (user_id, key, value) VALUES ({ph}, {ph}, {ph}) ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value"
    with _cursor() as cur:
        cur.execute(sql, (user_id, key, value))
