"""
Admin panel — only rendered for users with is_admin=True.

Sections:
  1. System Health   — DB, filesystem, Ollama, env checks
  2. Usage Stats     — per-user query/ingest/cloud counts, last activity
  3. User Management — storage, key reset, delete account
  4. Audit Log       — recent events across all users
"""

import os
import shutil
import sys
from pathlib import Path

import streamlit as st

from core.auth import delete_user, list_users
from core.database import (
    check_db_connection,
    get_recent_audit_log_all_users,
    get_user_activity_stats,
)
from core.model_router import is_ollama_running
from core.user_paths import get_key_path, get_user_dir, get_user_storage_bytes, get_vector_store_path


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


def render() -> None:
    st.title("🛡️ Admin Panel")
    current_user_id = st.session_state.get("user_id", "")

    tab_health, tab_stats, tab_users, tab_audit = st.tabs([
        "🩺 System Health",
        "📊 Usage Stats",
        "👥 User Management",
        "📋 Audit Log",
    ])

    # ── 1. System Health ──────────────────────────────────────────────────────
    with tab_health:
        st.subheader("System Health")

        col1, col2 = st.columns(2)

        # Database
        with col1:
            db_ok, db_msg = check_db_connection()
            if db_ok:
                st.success(f"✅ Database — {db_msg}")
            else:
                st.error(f"❌ Database — {db_msg}")

        # Ollama
        with col2:
            if is_ollama_running():
                st.success("✅ Ollama — running")
            else:
                st.info("ℹ️ Ollama — not running (cloud fallback active)")

        col3, col4 = st.columns(2)

        # DATA_DIR / volume
        with col3:
            data_dir = Path(os.environ.get("DATA_DIR", "data"))
            if data_dir.exists() and os.access(data_dir, os.W_OK):
                st.success(f"✅ Data volume — `{data_dir}` writable")
            elif data_dir.exists():
                st.warning(f"⚠️ Data volume — `{data_dir}` exists but not writable")
            else:
                st.error(f"❌ Data volume — `{data_dir}` does not exist")

        # OpenAI key
        with col4:
            if os.environ.get("OPENAI_API_KEY"):
                st.success("✅ OPENAI_API_KEY — set")
            else:
                st.warning("⚠️ OPENAI_API_KEY — not set (local model only)")

        st.divider()

        # Environment info
        st.subheader("Environment")
        env_info = {
            "Platform": sys.platform,
            "Python": sys.version.split()[0],
            "Railway environment": os.environ.get("RAILWAY_ENVIRONMENT", "not detected"),
            "Database backend": "PostgreSQL" if os.environ.get("DATABASE_URL") else "SQLite (local dev)",
            "DATA_DIR": os.environ.get("DATA_DIR", "data (default)"),
        }
        for key, val in env_info.items():
            col_k, col_v = st.columns([2, 3])
            col_k.caption(key)
            col_v.caption(f"`{val}`")

        st.divider()

        # Storage overview
        st.subheader("Storage")
        users = list_users()
        total_bytes = sum(get_user_storage_bytes(u["id"]) for u in users)
        data_dir_path = Path(os.environ.get("DATA_DIR", "data"))

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total users", len(users))
        col_b.metric("Total vector/key storage", _fmt_bytes(total_bytes))
        try:
            disk = shutil.disk_usage(data_dir_path if data_dir_path.exists() else ".")
            col_c.metric("Disk free", _fmt_bytes(disk.free))
        except Exception:
            col_c.metric("Disk free", "n/a")

    # ── 2. Usage Stats ────────────────────────────────────────────────────────
    with tab_stats:
        st.subheader("Usage Statistics")
        st.caption("Aggregated from the audit log — updated in real time.")

        users = list_users()
        activity = get_user_activity_stats()

        # Platform-wide totals
        total_queries     = sum(v["queries"]     for v in activity.values())
        total_ingestions  = sum(v["ingestions"]  for v in activity.values())
        total_cloud_calls = sum(v["cloud_calls"] for v in activity.values())
        total_errors      = sum(v["errors"]      for v in activity.values())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total queries", total_queries)
        c2.metric("Total ingestions", total_ingestions)
        c3.metric("☁️ Cloud API calls", total_cloud_calls)
        c4.metric("Errors", total_errors)

        st.divider()

        # Per-user table
        if not users:
            st.info("No users registered yet.")
        else:
            for user in users:
                uid = user["id"]
                stats = activity.get(uid, {
                    "queries": 0, "ingestions": 0, "errors": 0,
                    "cloud_calls": 0, "last_activity": "never", "doc_count": 0,
                })
                with st.expander(
                    f"**{user['username']}** — {stats['queries']} queries · "
                    f"{stats['doc_count']} docs · last active {stats['last_activity'] or 'never'}",
                    expanded=False,
                ):
                    col_a, col_b, col_c, col_d, col_e = st.columns(5)
                    col_a.metric("Queries", stats["queries"])
                    col_b.metric("Ingestions", stats["ingestions"])
                    col_c.metric("☁️ Cloud calls", stats["cloud_calls"])
                    col_d.metric("Errors", stats["errors"])
                    col_e.metric("Documents", stats["doc_count"])

                    local_pct = (
                        round((1 - stats["cloud_calls"] / stats["queries"]) * 100)
                        if stats["queries"] > 0 else 100
                    )
                    st.progress(local_pct / 100, text=f"{local_pct}% of queries stayed local")

    # ── 3. User Management ────────────────────────────────────────────────────
    with tab_users:
        st.subheader("User Management")
        st.caption("Admins are protected from deletion and key reset. You cannot act on your own account.")

        users = list_users()

        for user in users:
            uid = user["id"]
            storage = get_user_storage_bytes(uid)
            key_exists = get_key_path(uid).exists()
            is_self = uid == current_user_id

            with st.expander(
                f"**{user['username']}** {'(you)' if is_self else ''} "
                f"{'· Admin' if user['is_admin'] else '· User'} "
                f"· {_fmt_bytes(storage)} · key {'🔑 set' if key_exists else '⚠️ not set'}",
                expanded=False,
            ):
                col_info, col_actions = st.columns([3, 2])

                with col_info:
                    st.caption(f"User ID: `{uid}`")
                    st.caption(f"Joined: {user['created_at'][:10]}")
                    st.caption(f"Storage: {_fmt_bytes(storage)}")
                    st.caption(f"Encryption key: {'present' if key_exists else 'not set'}")

                with col_actions:
                    if is_self:
                        st.caption("No actions available on your own account.")
                    elif user["is_admin"]:
                        st.caption("Admin accounts are protected.")
                    else:
                        # Key reset
                        if key_exists:
                            if st.button(
                                "🔄 Reset encryption key",
                                key=f"reset_key_{uid}",
                                help="Deletes this user's key file and vector store. "
                                     "They will be locked out until they restore from their recovery phrase.",
                            ):
                                st.session_state[f"confirm_reset_{uid}"] = True

                            if st.session_state.get(f"confirm_reset_{uid}"):
                                st.warning(
                                    f"⚠️ This will **permanently lock {user['username']} out** of their "
                                    "encrypted data. They can only recover it with their 12-word phrase."
                                )
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button("Yes, reset key", key=f"confirm_yes_{uid}", type="primary"):
                                        _reset_user_key(uid, user["username"])
                                        st.session_state.pop(f"confirm_reset_{uid}", None)
                                with col_no:
                                    if st.button("Cancel", key=f"confirm_no_{uid}"):
                                        st.session_state.pop(f"confirm_reset_{uid}", None)
                                        st.rerun()
                        else:
                            st.caption("No key to reset.")

                        st.markdown("---")

                        # Delete account
                        if st.button(
                            "🗑️ Delete account",
                            key=f"del_user_{uid}",
                            help="Permanently deletes the account and all user data.",
                        ):
                            st.session_state[f"confirm_del_{uid}"] = True

                        if st.session_state.get(f"confirm_del_{uid}"):
                            st.error(
                                f"Delete **{user['username']}** and all their documents, "
                                "keys, and vector store? This cannot be undone."
                            )
                            col_yes2, col_no2 = st.columns(2)
                            with col_yes2:
                                if st.button("Yes, delete", key=f"del_yes_{uid}", type="primary"):
                                    _delete_user_and_data(uid, user["username"])
                                    st.session_state.pop(f"confirm_del_{uid}", None)
                            with col_no2:
                                if st.button("Cancel", key=f"del_no_{uid}"):
                                    st.session_state.pop(f"confirm_del_{uid}", None)
                                    st.rerun()

    # ── 4. Audit Log (all users) ──────────────────────────────────────────────
    with tab_audit:
        st.subheader("System-Wide Audit Log")
        st.caption("All events across all users — most recent first.")

        limit = st.slider("Events to show", 25, 500, 100, step=25)
        events = get_recent_audit_log_all_users(limit=limit)

        if not events:
            st.info("No events recorded yet.")
        else:
            # Build username lookup
            users = list_users()
            uid_to_name = {u["id"]: u["username"] for u in users}

            local_count  = sum(1 for e in events if e["local_only"])
            cloud_count  = len(events) - local_count
            error_count  = sum(1 for e in events if e["event_type"] == "error")

            c1, c2, c3 = st.columns(3)
            c1.metric("Events shown", len(events))
            c2.metric("🟢 Local", local_count)
            c3.metric("☁️ Cloud / ❌ Error", f"{cloud_count} / {error_count}")

            st.divider()

            import pandas as pd
            df = pd.DataFrame(events)
            df["user"] = df["user_id"].map(uid_to_name).fillna("unknown")
            df["local"] = df["local_only"].map(
                {1: "🟢 local", 0: "☁️ cloud", True: "🟢 local", False: "☁️ cloud"}
            )
            df["time"] = df["timestamp"].str[:19]
            display_df = df[["time", "user", "event_type", "model_used", "local"]].rename(columns={
                "time": "Time (UTC)",
                "user": "User",
                "event_type": "Event",
                "model_used": "Model",
                "local": "Where",
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reset_user_key(user_id: str, username: str) -> None:
    """Delete user's Fernet key file and vector store. They must restore from recovery phrase."""
    key_path = get_key_path(user_id)
    vector_path = get_vector_store_path(user_id)

    if key_path.exists():
        key_path.unlink()

    if vector_path.exists():
        shutil.rmtree(vector_path)

    st.success(
        f"🔄 Key reset for **{username}**. Their encrypted data is now inaccessible "
        "until they restore from their 12-word recovery phrase."
    )
    st.rerun()


def _delete_user_and_data(user_id: str, username: str) -> None:
    """Remove user account record from DB and purge their entire data directory."""
    delete_user(user_id)
    user_dir = get_user_dir(user_id)
    if user_dir.exists():
        shutil.rmtree(user_dir)
    st.success(f"🗑️ Deleted user **{username}** and all their data.")
    st.rerun()
