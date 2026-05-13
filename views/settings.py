"""
Settings page: model configuration, routing thresholds, audit log, deployment notes.
Settings are stored per-user at data/users/{user_id}/settings.yaml.
"""

import json
from pathlib import Path

import streamlit as st
import yaml

from core.audit import log
from core.database import get_audit_log
from core.model_router import get_available_ollama_models, is_ollama_running
from core.user_paths import get_settings_path


def _load_settings(settings_path: Path) -> dict:
    if settings_path.exists():
        with open(settings_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_settings(settings: dict, settings_path: Path) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w") as f:
        yaml.dump(settings, f, default_flow_style=False)


def render(user_id: str) -> None:
    settings_path = get_settings_path(user_id)

    st.title("⚙️ Settings")

    settings = _load_settings(settings_path)

    # --- API Keys ---
    st.subheader("API Keys")
    st.caption("Your API key is stored only in your per-user settings file — never in shared storage.")
    openai_key = st.text_input(
        "OpenAI API Key",
        value=settings.get("openai_api_key", ""),
        type="password",
        help="Required for cloud model fallback and optional OpenAI embeddings. Get yours at platform.openai.com.",
    )

    st.divider()

    # --- Model Configuration ---
    st.subheader("AI Model Configuration")
    st.caption(
        "PrivateAI automatically routes simple queries to your local model (free, private) "
        "and complex queries to OpenAI (more capable, but sends data externally)."
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Local model (Ollama)**")
        if is_ollama_running():
            available_models = get_available_ollama_models()
            default_local = settings.get("local_model", "llama3")
            if available_models:
                local_model = st.selectbox(
                    "Select local model",
                    options=available_models,
                    index=available_models.index(default_local) if default_local in available_models else 0,
                )
            else:
                st.warning("No models pulled in Ollama yet.")
                st.caption("Run `ollama pull llama3` in a terminal to download a model.")
                local_model = st.text_input("Local model name", value=default_local)
        else:
            st.info("Ollama not running — cloud model only")
            st.caption("Install Ollama from ollama.com to enable fully local, private queries.")
            local_model = st.text_input(
                "Model name (for when Ollama is available)",
                value=settings.get("local_model", "llama3"),
            )

    with col2:
        st.markdown("**Cloud model (OpenAI)**")
        openai_model = st.selectbox(
            "OpenAI fallback model",
            options=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            index=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"].index(
                settings.get("openai_model", "gpt-4o")
            ),
            help="Used when Ollama is unavailable or the query is too complex for the local model.",
        )

    st.divider()

    # --- Routing ---
    st.subheader("Smart Routing Threshold")
    st.markdown(
        "PrivateAI scores each query for complexity. "
        "Queries **below** the threshold go to your local model (private). "
        "Queries **at or above** it escalate to OpenAI (more capable)."
    )
    threshold = st.slider(
        "Complexity threshold",
        min_value=0, max_value=100,
        value=int(settings.get("complexity_threshold", 60)),
        step=5,
        help="Set lower to use local model more often. Set higher to use OpenAI more often.",
    )
    with st.expander("What affects the complexity score?"):
        st.markdown("""
| Signal | Score added |
|---|---|
| Query > 50 words | +20 |
| Contains code block | +25 |
| Contains math/formulas | +20 |
| > 5 document passages retrieved | +15 |
| > 10 conversation turns | +10 |
        """)

    st.divider()

    # --- Embeddings ---
    st.subheader("Embedding Provider")
    embed_provider = st.radio(
        "How should documents be indexed?",
        options=["local", "openai"],
        index=0 if settings.get("embedding_provider", "local") == "local" else 1,
        horizontal=True,
        help="Local = sentence-transformers (offline, private). OpenAI = higher quality but sends text to OpenAI during ingestion.",
    )
    if embed_provider == "local":
        st.success("🟢 Local embeddings — document text never leaves this machine during indexing.")
    else:
        st.warning(
            "⚠️ OpenAI embeddings send your document text to OpenAI's servers during ingestion. "
            "This breaks the fully-local privacy guarantee. Only use if you've accepted this trade-off."
        )

    st.divider()

    # --- Save settings ---
    if st.button("Save Settings", type="primary"):
        new_settings = {
            "openai_api_key": openai_key,
            "local_model": local_model,
            "openai_model": openai_model,
            "complexity_threshold": threshold,
            "embedding_provider": embed_provider,
        }
        _save_settings(new_settings, settings_path)
        st.session_state["settings"] = new_settings
        log("settings_change", user_id=user_id, details={"keys_changed": list(new_settings.keys())})
        st.success("✅ Settings saved.")

    st.divider()

    # --- Audit Log ---
    st.subheader("📋 Your Privacy Audit Log")
    st.caption("Every query and ingestion event is logged so you can see exactly what your AI did and where data went.")

    audit_rows = get_audit_log(user_id=user_id, limit=100)
    if not audit_rows:
        st.info("No events logged yet. Start chatting to see your audit trail here.")
    else:
        local_count = sum(1 for r in audit_rows if r["local_only"])
        cloud_count = len(audit_rows) - local_count
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total events", len(audit_rows))
        col_b.metric("🟢 Stayed local", local_count)
        col_c.metric("☁️ Used cloud API", cloud_count)

        with st.expander("View recent events", expanded=False):
            import pandas as pd
            df = pd.DataFrame(audit_rows)[["timestamp", "event_type", "model_used", "local_only"]]
            df["local_only"] = df["local_only"].map({1: "Yes", 0: "No", True: "Yes", False: "No"})
            df["timestamp"] = df["timestamp"].str[:19]
            df.columns = ["Time (UTC)", "Event", "Model", "Stayed Local?"]
            st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # --- Deployment section ---
    st.subheader("☁️ Cloud Deployment")
    with st.expander("Deploy to Railway (recommended)", expanded=False):
        st.markdown("""
**One-click Railway deployment:**

1. Fork this repo to your GitHub account
2. Create a new Railway project → **New Service → GitHub Repo**
3. Add a **PostgreSQL** database service (Railway provides one free)
4. Set environment variables:
   - `DATABASE_URL` — auto-populated by Railway from the PostgreSQL service
   - `OPENAI_API_KEY` — your OpenAI key
   - `DATA_DIR` — set to `/app/data`
5. Create a **Volume** and mount it at `/app/data` (stores your encryption keys + vector store)
6. Deploy — Railway will build and start the app automatically

See the full guide in the repository README.
        """)
