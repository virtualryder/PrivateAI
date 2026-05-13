"""
User account management for PrivateAI.

Stores usernames + bcrypt-hashed passwords in the shared database
(PostgreSQL on Railway, SQLite locally). Uses the connection layer
from core.database so there is one DB config throughout the app.

Rules:
- Usernames are lowercased and unique.
- The first user to register becomes admin automatically.
- Admins can view and delete non-admin users via the admin panel.
- Passwords must be ≥ 8 characters.
"""

import uuid
from datetime import datetime, timezone

import bcrypt

from core.database import _cursor, _ph, init_db


def init_users_db() -> None:
    """Ensure the users table exists. Delegates to init_db() — safe to call repeatedly."""
    init_db()


def user_count() -> int:
    ph = _ph()
    with _cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM users")
        row = cur.fetchone()
        return row["n"]


def create_user(username: str, password: str) -> str:
    """
    Create a new user account. Returns the new user_id (UUID).
    The first user created is automatically made admin.
    Raises ValueError for validation errors, IntegrityError on duplicate username.
    """
    username = username.strip().lower()
    if not username:
        raise ValueError("Username cannot be empty.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = str(uuid.uuid4())
    is_admin_val = True if user_count() == 0 else False
    now = datetime.now(timezone.utc).isoformat()

    ph = _ph()
    # Normalize bool for backend
    from core.database import _USE_PG, _bool_val
    with _cursor() as cur:
        cur.execute(
            f"INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
            (user_id, username, pw_hash, _bool_val(is_admin_val), now),
        )
    return user_id


def authenticate(username: str, password: str) -> dict | None:
    """
    Verify credentials. Returns the full user row as a dict on success, None on failure.
    Uses constant-time comparison via bcrypt to prevent timing-based username enumeration.
    """
    username = username.strip().lower()
    ph = _ph()
    with _cursor() as cur:
        cur.execute(f"SELECT * FROM users WHERE username={ph}", (username,))
        row = cur.fetchone()

    if row is None:
        # Dummy check to prevent username enumeration via timing
        bcrypt.checkpw(b"dummy", bcrypt.hashpw(b"dummy", bcrypt.gensalt()))
        return None

    if bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return dict(row)
    return None


def list_users() -> list[dict]:
    """Return all users (id, username, is_admin, created_at). No password hashes."""
    with _cursor() as cur:
        cur.execute(
            "SELECT id, username, is_admin, created_at FROM users ORDER BY created_at"
        )
        return [dict(r) for r in cur.fetchall()]


def delete_user(user_id: str) -> None:
    """Remove a user account record. Does NOT delete their data directory."""
    ph = _ph()
    with _cursor() as cur:
        cur.execute(f"DELETE FROM users WHERE id={ph}", (user_id,))
