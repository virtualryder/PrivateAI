"""
PrivateAI — Private AI Agent Platform

Entry point. Handles (in order):
  1. DB init    — create tables if they don't exist (once per startup)
  2. Auth gate  — no session user_id → show login/signup page
  3. Key gate   — user logged in but no encryption key → go to Onboarding
  4. Sidebar    — username, key fingerprint, model indicator, logout
  5. Page routing — Onboarding / Ingest Documents / Chat / Settings / Admin
"""

from pathlib import Path

import streamlit as st
import yaml
from cryptography.fernet import Fernet

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PrivateAI",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB init (runs once per container/process startup) ─────────────────────────
from core.database import init_db
init_db()

# ── Session state defaults ────────────────────────────────────────────────────
_DEFAULTS = dict(
    # Auth
    user_id=None,
    username=None,
    is_admin=False,
    # Encryption
    fernet_key=None,
    key_fingerprint=None,
    # App state
    chat_history=[],
    ingestion_log=[],
    settings={},
    last_model_used=None,
    routing_reason=None,
    page="Onboarding",
)
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Auth gate — must be first ─────────────────────────────────────────────────
if st.session_state["user_id"] is None:
    from pages import auth as auth_page
    auth_page.render()
    st.stop()

user_id: str = st.session_state["user_id"]

# ── Per-user paths (filesystem — keys, vector store, settings) ────────────────
from core.user_paths import get_key_path, get_settings_path

_key_path = get_key_path(user_id)
_settings_path = get_settings_path(user_id)

# ── Settings loader (per-user YAML) ──────────────────────────────────────────
def _load_settings() -> dict:
    if _settings_path.exists():
        with open(_settings_path) as f:
            return yaml.safe_load(f) or {}
    return {}

if not st.session_state["settings"]:
    st.session_state["settings"] = _load_settings()

# ── Key gate ──────────────────────────────────────────────────────────────────
if st.session_state["fernet_key"] is None:
    if _key_path.exists():
        from core.crypto import get_fernet, key_fingerprint
        from core.audit import log
        key_bytes = _key_path.read_bytes()
        st.session_state["fernet_key"] = get_fernet(key_bytes)
        st.session_state["key_fingerprint"] = key_fingerprint(key_bytes)
        log("key_load", user_id=user_id, details={"fingerprint": st.session_state["key_fingerprint"]})

# ── Embedding function (shared cache — keyed by provider + api_key) ───────────
@st.cache_resource(show_spinner="Loading embedding model...")
def _get_embedding_fn(provider: str, openai_api_key: str):
    from core.embeddings import get_embedding_function
    return get_embedding_function(provider, openai_api_key or None)

settings = st.session_state["settings"]
_embedding_fn = _get_embedding_fn(
    provider=settings.get("embedding_provider", "local"),
    openai_api_key=settings.get("openai_api_key", ""),
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔒 PrivateAI")

    username = st.session_state.get("username", "")
    is_admin = st.session_state.get("is_admin", False)
    admin_label = " · Admin" if is_admin else ""
    st.caption(f"Signed in as **{username}**{admin_label}")

    fp = st.session_state.get("key_fingerprint")
    if fp:
        st.caption(f"🔑 Key `{fp}` · Encrypted")
    else:
        st.caption("⚠️ No encryption key loaded")

    st.markdown("---")

    last_model = st.session_state.get("last_model_used")
    if last_model:
        is_local = last_model.startswith("ollama/")
        icon = "🟢 LOCAL" if is_local else "☁️ CLOUD"
        st.caption(f"Last query: **{icon}**")
        st.caption(last_model)
        st.markdown("---")

    # Navigation
    _PAGE_NAMES = ["Onboarding", "Ingest Documents", "Chat", "Settings"]
    if is_admin:
        _PAGE_NAMES.append("Admin")

    default_page = st.session_state.get("page", "Onboarding")
    if default_page not in _PAGE_NAMES:
        default_page = "Onboarding"

    selected_page = st.radio(
        "Navigate",
        options=_PAGE_NAMES,
        index=_PAGE_NAMES.index(default_page),
        key="nav_radio",
    )
    st.session_state["page"] = selected_page

    st.markdown("---")
    if st.button("Logout", use_container_width=True):
        for _key in list(st.session_state.keys()):
            del st.session_state[_key]
        st.rerun()

# ── Page routing ──────────────────────────────────────────────────────────────
page = st.session_state["page"]
fernet: Fernet | None = st.session_state["fernet_key"]

# All pages except Onboarding and Admin require a loaded key
if page not in ("Onboarding", "Admin") and fernet is None:
    st.error("No encryption key loaded. Please complete setup first.")
    from pages import onboarding
    onboarding.render(user_id=user_id)
    st.stop()

if page == "Onboarding":
    from pages import onboarding
    onboarding.render(user_id=user_id)

elif page == "Ingest Documents":
    from pages import ingestion_ui
    ingestion_ui.render(embedding_fn=_embedding_fn, fernet=fernet, user_id=user_id)

elif page == "Chat":
    from pages import chat
    chat.render(
        fernet=fernet,
        embedding_fn=_embedding_fn,
        settings=st.session_state["settings"],
        user_id=user_id,
    )

elif page == "Settings":
    from pages import settings as settings_page
    settings_page.render(user_id=user_id)
    st.session_state["settings"] = _load_settings()

elif page == "Admin":
    if not st.session_state.get("is_admin"):
        st.error("Access denied.")
    else:
        from pages import admin
        admin.render()
