"""
Chat page — main interaction interface.

Features:
- Conversational chat with message history
- Source citations from retrieved document chunks
- Model indicator on every response (local vs cloud)
- Privacy indicator: shows if response required an external API call
"""

import streamlit as st
from cryptography.fernet import Fernet
from typing import Callable

from core.database import list_documents
from core.user_paths import get_vector_store_path
from rag.chain import ask


def render(
    fernet: Fernet,
    embedding_fn: Callable,
    settings: dict,
    user_id: str,
) -> None:
    vector_store_path = get_vector_store_path(user_id)

    st.title("💬 Chat with Your Documents")

    docs = list_documents(user_id=user_id)
    enabled_ids = [d["id"] for d in docs if d["enabled"]]

    if not docs:
        st.warning(
            "Your knowledge base is empty. Go to **Ingest Documents** to add your files first."
        )
        return

    if not enabled_ids:
        st.warning(
            "All documents are currently disabled. Go to **Ingest Documents** "
            "and toggle at least one document to Active."
        )
        return

    col_info, col_privacy = st.columns([3, 1])
    with col_info:
        st.caption(f"Querying **{len(enabled_ids)}** of {len(docs)} document(s)")
    with col_privacy:
        st.caption("🔒 Your data never leaves without your consent")

    # --- Settings sidebar for this page ---
    with st.sidebar:
        st.markdown("**Query Settings**")
        force_openai = st.checkbox(
            "Force cloud model (GPT-4o)",
            value=False,
            key="force_openai",
            help="Routes all queries to OpenAI's GPT-4o regardless of complexity score. Requires your API key.",
        )
        top_k = st.slider(
            "Passages to retrieve",
            1, 10, 5,
            key="top_k",
            help="How many document passages to search before answering. More = broader context.",
        )
        show_context = st.checkbox(
            "Show retrieved passages",
            value=False,
            key="show_ctx",
            help="Display the raw document text the AI used to form its answer.",
        )

    # --- Initialize chat history ---
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # --- Display existing messages ---
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                _render_response_footer(
                    msg.get("routing_reason", ""),
                    msg.get("local_only", True),
                    msg.get("sources", []),
                    show_context,
                    msg.get("context_used", ""),
                )

    # --- Chat input ---
    question = st.chat_input("Ask anything about your documents…")

    if question:
        st.session_state["chat_history"].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching your documents and thinking…"):
                try:
                    result = ask(
                        question=question,
                        fernet=fernet,
                        embedding_fn=embedding_fn,
                        openai_api_key=settings.get("openai_api_key"),
                        session_turn_count=len(st.session_state["chat_history"]),
                        local_model=settings.get("local_model", "llama3"),
                        openai_model=settings.get("openai_model", "gpt-4o"),
                        complexity_threshold=int(settings.get("complexity_threshold", 60)),
                        top_k=top_k,
                        force_openai=force_openai,
                        enabled_doc_ids=enabled_ids,
                        user_id=user_id,
                    )
                    st.markdown(result["answer"])
                    _render_response_footer(
                        result["routing_reason"],
                        result["local_only"],
                        result["sources"],
                        show_context,
                        result["context_used"],
                    )

                    st.session_state["chat_history"].append({
                        "role": "assistant",
                        "content": result["answer"],
                        "routing_reason": result["routing_reason"],
                        "local_only": result["local_only"],
                        "sources": result["sources"],
                        "context_used": result["context_used"],
                    })
                    st.session_state["last_model_used"] = result["routing_reason"]
                    st.session_state["routing_reason"] = result["routing_reason"]

                except Exception as exc:
                    st.error(f"Something went wrong: {exc}")
                    st.caption("If using OpenAI, check your API key in **Settings**.")

    # --- Clear history button ---
    if st.session_state["chat_history"]:
        if st.button("Clear conversation", key="clear_chat"):
            st.session_state["chat_history"] = []
            st.rerun()


def _render_response_footer(
    routing_reason: str,
    local_only: bool,
    sources: list[dict],
    show_context: bool,
    context_used: str,
) -> None:
    if local_only:
        badge = "🟢 LOCAL — your data stayed on this machine"
    else:
        badge = "☁️ CLOUD — query was sent to OpenAI's API"

    col_model, col_badge = st.columns([2, 2])
    with col_model:
        st.caption(f"Answered by: `{routing_reason}`")
    with col_badge:
        st.caption(badge)

    if sources:
        with st.expander(f"📄 Sources ({len(sources)} passage(s) used)", expanded=False):
            for s in sources:
                st.caption(f"- **{s['filename']}**, passage {s['chunk_index']}")

    if show_context and context_used:
        with st.expander("🔍 Retrieved passages (raw)", expanded=False):
            st.text(context_used[:3000])
