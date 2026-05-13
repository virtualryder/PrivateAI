"""
LangChain LCEL RAG chain.

Builds a simple retrieval-augmented generation chain:
  context (from retriever) + question → prompt → routed LLM → answer

Returns both the answer string and the routing reason so the UI can display
which model was used. All retrieval is scoped to the calling user's vector store.
"""

from __future__ import annotations

from typing import Callable

from cryptography.fernet import Fernet
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from core.audit import log
from core.model_router import get_llm, routing_is_local
from core.user_paths import get_vector_store_path
from rag.retriever import retrieve_context


_SYSTEM_PROMPT = """You are a private AI assistant with access only to the user's personal documents.

RULES:
1. Answer based ONLY on the provided context from the user's documents.
2. If the answer is not in the context, say exactly: "I don't have that information in your documents."
3. Never fabricate facts or make up citations.
4. Cite the source document and chunk number when possible.
5. Keep answers concise unless the user explicitly asks for detail.

CONTEXT FROM YOUR DOCUMENTS:
{context}"""


def ask(
    question: str,
    fernet: Fernet,
    embedding_fn: Callable,
    openai_api_key: str | None,
    user_id: str,
    session_turn_count: int = 0,
    local_model: str = "llama3",
    openai_model: str = "gpt-4o",
    complexity_threshold: int = 60,
    top_k: int = 5,
    force_openai: bool = False,
    enabled_doc_ids: list[str] | None = None,
) -> dict:
    """
    Run a RAG query against the user's private knowledge base.

    Returns:
    {
        "answer": str,
        "routing_reason": str,
        "sources": list[dict],
        "context_used": str,
        "local_only": bool,
    }
    """
    vector_store_path = get_vector_store_path(user_id)

    # --- Retrieve context from user's vector store ---
    context, sources = retrieve_context(
        query=question,
        fernet=fernet,
        embedding_fn=embedding_fn,
        vector_store_path=vector_store_path,
        top_k=top_k,
        enabled_doc_ids=enabled_doc_ids,
    )

    if not context:
        context = "(No relevant documents found in your knowledge base)"

    # --- Route to appropriate LLM ---
    llm, routing_reason = get_llm(
        query=question,
        retrieved_chunk_count=len(sources),
        session_turn_count=session_turn_count,
        local_model=local_model,
        openai_model=openai_model,
        openai_api_key=openai_api_key,
        complexity_threshold=complexity_threshold,
        force_openai=force_openai,
    )

    # --- Build and run the chain ---
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"context": context, "question": question})

    is_local = routing_is_local(routing_reason)

    log(
        "query",
        user_id=user_id,
        details={"question": question[:200], "sources": len(sources), "routing": routing_reason},
        model_used=routing_reason,
        local_only=is_local,
    )

    return {
        "answer": answer,
        "routing_reason": routing_reason,
        "sources": sources,
        "context_used": context,
        "local_only": is_local,
    }
