"""
Document Ingestion page.

Upload files → ingest into encrypted private knowledge base.
Shows ingestion progress, document list with enable/disable toggles.
All data is scoped to the current user via user_id.

Upload limit: 250 MB per file (enforced in pipeline.py and UI).
"""

import streamlit as st
from pathlib import Path

from core.database import list_documents, set_document_enabled, delete_document
from core.user_paths import get_vector_store_path, get_upload_dir, get_user_storage_bytes
from ingestion.loader import SUPPORTED_EXTENSIONS
from ingestion.pipeline import cleanup_upload, ingest_file, save_upload, delete_document_from_store, _MAX_UPLOAD_BYTES

_MAX_UPLOAD_MB = _MAX_UPLOAD_BYTES // (1024 * 1024)


def _fmt_bytes(n: int) -> str:
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


def render(embedding_fn, fernet, user_id: str) -> None:
    vector_store_path = get_vector_store_path(user_id)
    upload_dir = get_upload_dir(user_id)

    st.title("📂 Ingest Documents")
    st.markdown(
        "Add your personal documents to your private knowledge base. "
        "**All text is encrypted before storage** using your unique key — "
        "only you can read it, even if the server is compromised."
    )

    with st.expander("🔒 How your data stays private", expanded=False):
        st.markdown("""
- **Encryption at rest**: Each text chunk is encrypted with your Fernet key before being stored.
- **Vectors are safe**: Only numerical embeddings (not your text) go into the vector store.
- **Your key, your data**: The encryption key lives only in your browser session and on your chosen device.
- **Zero shared storage**: Your documents are isolated from every other user's data.
        """)

    supported = ", ".join(SUPPORTED_EXTENSIONS)
    st.caption(f"Supported formats: {supported} · Max file size: {_MAX_UPLOAD_MB} GB per file")

    # --- Upload widget ---
    uploaded_files = st.file_uploader(
        "Drop files here or click to browse",
        type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS],
        accept_multiple_files=True,
        key="file_uploader",
        help=f"Select one or more files (max {_MAX_UPLOAD_MB} MB each). Zip folders before uploading.",
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        chunk_size = st.number_input(
            "Chunk size (chars)",
            min_value=200, max_value=4000, value=800, step=100,
            help="How many characters per chunk. Smaller = more precise answers. Larger = more context per result.",
        )
    with col2:
        st.caption(" ")
        force_reingest = st.checkbox(
            "Re-ingest already-processed files",
            value=False,
            help="By default, identical files are skipped. Check this to force re-processing.",
        )

    if uploaded_files and st.button("Ingest Selected Files", type="primary"):
        results = []
        progress = st.progress(0)
        status_area = st.empty()

        for i, uploaded in enumerate(uploaded_files):
            status_area.info(f"Processing **{uploaded.name}**...")
            file_path = save_upload(uploaded, upload_dir=upload_dir)
            result = ingest_file(
                file_path=file_path,
                fernet=fernet,
                embedding_fn=embedding_fn,
                chunk_size=chunk_size,
                force=force_reingest,
                user_id=user_id,
            )
            cleanup_upload(file_path)
            results.append(result)
            progress.progress((i + 1) / len(uploaded_files))

        status_area.empty()
        progress.empty()

        ingested = [r for r in results if r["status"] == "ingested"]
        skipped = [r for r in results if r["status"] == "skipped"]
        errors = [r for r in results if r["status"] == "error"]

        if ingested:
            st.success(f"✅ Ingested {len(ingested)} file(s): {', '.join(r['filename'] for r in ingested)}")
        if skipped:
            st.info(f"⏭️ Skipped {len(skipped)} already-ingested file(s)")
        if errors:
            for r in errors:
                st.error(f"❌ **{r['filename']}**: {r['message']}")

        st.session_state["ingestion_log"] = results

    st.divider()

    # --- Document library ---
    st.subheader("Your Knowledge Base")

    storage_bytes = get_user_storage_bytes(user_id)
    docs = list_documents(user_id=user_id)

    col_hdr1, col_hdr2 = st.columns([3, 1])
    with col_hdr1:
        if docs:
            enabled_count = sum(1 for d in docs if d["enabled"])
            st.caption(f"{len(docs)} document(s) — {enabled_count} active for queries")
        else:
            st.info("No documents ingested yet. Upload files above to get started.")
    with col_hdr2:
        if storage_bytes > 0:
            st.caption(f"Storage: {_fmt_bytes(storage_bytes)}")

    for doc in docs:
        col_name, col_chunks, col_toggle, col_delete = st.columns([4, 1, 1, 1])
        with col_name:
            st.markdown(f"**{doc['filename']}**")
            st.caption(f"ID: {doc['id'][:8]}… · Added: {doc['ingested_at'][:10]}")
        with col_chunks:
            st.metric("Chunks", doc["chunk_count"])
        with col_toggle:
            enabled = st.toggle(
                "Active",
                value=bool(doc["enabled"]),
                key=f"toggle_{doc['id']}",
                help="Toggle to include or exclude this document from AI queries",
            )
            if enabled != bool(doc["enabled"]):
                set_document_enabled(doc["id"], enabled, user_id=user_id)
                st.rerun()
        with col_delete:
            if st.button("🗑️", key=f"del_{doc['id']}", help="Permanently delete from knowledge base"):
                delete_document_from_store(doc["id"], user_id=user_id)
                delete_document(doc["id"], user_id=user_id)
                st.rerun()
