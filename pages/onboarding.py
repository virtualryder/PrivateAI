"""
Onboarding page: encryption key setup and system health checks.

Two paths:
  A) Generate new key → show 12-word recovery phrase → confirm 3 random words → save
  B) Restore from phrase → validate → save

After key is saved and loaded into session state, user is redirected to Ingest Documents.
Key is stored at data/users/{user_id}/.key — isolated per user, never shared.
"""

import streamlit as st
from cryptography.fernet import Fernet

from core.crypto import (
    generate_key_and_phrase,
    get_fernet,
    key_fingerprint,
    restore_key_from_phrase,
    save_key,
)
from core.model_router import get_available_ollama_models, is_ollama_running
from core.user_paths import get_key_path


def _load_key_to_session(key_bytes: bytes) -> None:
    st.session_state["fernet_key"] = get_fernet(key_bytes)
    st.session_state["key_fingerprint"] = key_fingerprint(key_bytes)


def render(user_id: str) -> None:
    key_path = get_key_path(user_id)

    st.title("🔒 PrivateAI — Setup")
    st.markdown(
        "Welcome to **PrivateAI**. Before you can chat with your documents, "
        "you need to create an **encryption key**. This key is the only thing "
        "that can unlock your data — not even the server can read it without it."
    )

    with st.expander("ℹ️ Why do I need an encryption key?", expanded=False):
        st.markdown("""
Your documents are encrypted **before** they are stored. The encryption key is:

- **Generated on your device** — never sent to any server
- **Required to read your data** — if you lose it, your data cannot be recovered
- **Backed up with a 12-word phrase** — write it down and keep it safe, like a bank PIN

This design means that even if the database or server is breached, your documents are unreadable.
        """)

    # --- System health status ---
    st.divider()
    st.subheader("System Status")
    col1, col2 = st.columns(2)
    with col1:
        if is_ollama_running():
            models = get_available_ollama_models()
            st.success(f"✅ Local AI ready — {len(models)} model(s) available")
            if models:
                st.caption(", ".join(models[:5]))
        else:
            st.info("☁️ Local AI not running — will use OpenAI as fallback")
            st.caption("Install Ollama (ollama.com) to enable fully offline, private mode")
    with col2:
        openai_key = st.session_state.get("settings", {}).get("openai_api_key", "")
        if openai_key:
            st.success("✅ OpenAI API key configured")
        else:
            st.info("ℹ️ OpenAI API key not set")
            st.caption("Add your key in Settings after completing setup")

    st.divider()

    # If key already exists on disk, offer to load it
    if key_path.exists():
        fp = key_fingerprint(key_path.read_bytes())
        st.info(f"🔑 Existing key found for this account — fingerprint: `{fp}`")
        if st.button("Load my existing key and continue", type="primary"):
            key_bytes = key_path.read_bytes()
            _load_key_to_session(key_bytes)
            st.success("Key loaded. Taking you to your knowledge base…")
            st.session_state["page"] = "Ingest Documents"
            st.rerun()
        st.caption("Or set up a new key below (this will replace your existing key).")
        st.divider()

    tab_new, tab_restore = st.tabs(["🆕 Generate New Key", "🔁 Restore from Recovery Phrase"])

    # --- Tab A: Generate new key ---
    with tab_new:
        st.markdown(
            "We'll generate a secure encryption key and give you a **12-word recovery phrase**. "
            "Write the phrase down on paper and store it somewhere safe — "
            "it's the only way to recover your data if you lose access to this device."
        )
        if st.button("Generate My Key + Recovery Phrase", key="gen_btn", type="primary"):
            key_bytes, phrase = generate_key_and_phrase()
            st.session_state["_gen_key_bytes"] = key_bytes
            st.session_state["_gen_phrase"] = phrase
            st.session_state["_confirm_indices"] = [2, 6, 10]

        if "_gen_phrase" in st.session_state:
            phrase = st.session_state["_gen_phrase"]
            words = phrase.split()

            st.warning("⚠️ Write these 12 words down **in order**. Do NOT save them in a file or screenshot.")
            cols = st.columns(4)
            for i, word in enumerate(words):
                cols[i % 4].markdown(f"**{i+1}.** `{word}`")

            st.markdown("**Confirm you wrote them down** — enter the words at the positions below:")
            confirm_indices = st.session_state.get("_confirm_indices", [2, 6, 10])
            inputs = {}
            c1, c2, c3 = st.columns(3)
            cols_confirm = [c1, c2, c3]
            for ci, idx in enumerate(confirm_indices):
                inputs[idx] = cols_confirm[ci].text_input(
                    f"Word #{idx + 1}", key=f"confirm_{idx}"
                ).strip().lower()

            if st.button("Confirm and Activate Key", key="confirm_btn", type="primary"):
                correct = all(inputs[idx] == words[idx] for idx in confirm_indices)
                if not correct:
                    wrong = [f"#{idx+1}" for idx in confirm_indices if inputs[idx] != words[idx]]
                    st.error(f"Incorrect words at position(s): {', '.join(wrong)}. Check your written phrase.")
                else:
                    key_bytes = st.session_state["_gen_key_bytes"]
                    save_key(key_bytes, key_path)
                    _load_key_to_session(key_bytes)
                    for k in ["_gen_key_bytes", "_gen_phrase", "_confirm_indices"]:
                        st.session_state.pop(k, None)
                    st.success("🎉 Key saved. Your account is now encrypted and ready.")
                    st.session_state["page"] = "Ingest Documents"
                    st.rerun()

    # --- Tab B: Restore from phrase ---
    with tab_restore:
        st.markdown(
            "If you previously set up PrivateAI and saved your 12-word recovery phrase, "
            "enter it below to restore access to your encrypted data."
        )
        phrase_input = st.text_area(
            "Recovery phrase (12 words, space-separated)",
            placeholder="word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12",
            height=100,
            key="restore_phrase_input",
        )
        if st.button("Restore My Key", key="restore_btn", type="primary"):
            try:
                key_bytes = restore_key_from_phrase(phrase_input.strip())
                save_key(key_bytes, key_path)
                _load_key_to_session(key_bytes)
                st.success(f"✅ Key restored. Fingerprint: `{key_fingerprint(key_bytes)}`")
                st.session_state["page"] = "Ingest Documents"
                st.rerun()
            except ValueError as e:
                st.error(str(e))
