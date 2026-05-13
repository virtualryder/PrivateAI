"""
Admin panel — only rendered for users with is_admin=True.

Capabilities:
  - View all registered users with storage usage
  - Delete non-admin users and purge their data directory
  - View system-wide storage totals
"""

import shutil

import streamlit as st

from core.auth import delete_user, list_users
from core.user_paths import get_user_dir, get_user_storage_bytes


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


def render() -> None:
    st.title("Admin Panel")

    current_user_id = st.session_state.get("user_id", "")
    users = list_users()

    # ── User table ────────────────────────────────────────────────────────────
    st.subheader(f"Registered Users ({len(users)})")

    total_bytes = 0
    for user in users:
        storage = get_user_storage_bytes(user["id"])
        total_bytes += storage

        col_name, col_role, col_storage, col_action = st.columns([4, 1, 2, 1])
        with col_name:
            st.markdown(f"**{user['username']}**")
            st.caption(f"ID: `{user['id'][:8]}...` | Joined: {user['created_at'][:10]}")
        with col_role:
            if user["is_admin"]:
                st.markdown("Admin")
            else:
                st.markdown("User")
        with col_storage:
            st.caption(_fmt_bytes(storage))
        with col_action:
            # Cannot delete yourself or other admins
            if user["id"] == current_user_id:
                st.caption("(you)")
            elif user["is_admin"]:
                st.caption("protected")
            else:
                if st.button("Delete", key=f"del_user_{user['id']}"):
                    _delete_user_and_data(user["id"], user["username"])

    st.divider()

    # ── System totals ─────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    col_a.metric("Total users", len(users))
    col_b.metric("Total storage used", _fmt_bytes(total_bytes))


def _delete_user_and_data(user_id: str, username: str) -> None:
    """Remove user record from DB and purge their entire data directory."""
    delete_user(user_id)
    user_dir = get_user_dir(user_id)
    if user_dir.exists():
        shutil.rmtree(user_dir)
    st.success(f"Deleted user '{username}' and all their data.")
    st.rerun()
