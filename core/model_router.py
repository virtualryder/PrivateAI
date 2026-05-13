"""
Hybrid model router.

Decision logic:
  1. Is Ollama reachable? (GET localhost:11434/api/tags, timeout=2s)
     NO  → openai (reason: ollama_unavailable)
  2. Is the configured local model pulled?
     NO  → openai (reason: model_not_pulled)
  3. Score query complexity (0–100). If score < threshold → ollama, else → openai.

Every call returns (llm_instance, routing_reason_string) so the UI can display
which model answered and why.
"""

from __future__ import annotations

import re
import requests
from langchain_core.language_models import BaseChatModel


import os
_OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_DEFAULT_LOCAL_MODEL = "llama3"
_DEFAULT_OPENAI_MODEL = "gpt-4o"
_DEFAULT_THRESHOLD = 60


def is_ollama_running(base_url: str = _OLLAMA_BASE_URL) -> bool:
    """Return True if the Ollama daemon is reachable."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def get_available_ollama_models(base_url: str = _OLLAMA_BASE_URL) -> list[str]:
    """Return list of pulled model names from Ollama. Empty list if unavailable."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=2)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def _is_model_available(model_name: str, base_url: str = _OLLAMA_BASE_URL) -> bool:
    """Check if a specific model is pulled in Ollama."""
    available = get_available_ollama_models(base_url)
    # Allow partial match (e.g. "llama3" matches "llama3:latest")
    return any(model_name in m for m in available)


def _complexity_score(
    query: str,
    retrieved_chunk_count: int = 0,
    session_turn_count: int = 0,
    force_openai: bool = False,
) -> int:
    """
    Score query complexity from 0 to 100+.
    Higher score → more likely to route to OpenAI.
    """
    if force_openai:
        return 100

    score = 0

    # Long query
    if len(query.split()) > 50:
        score += 20

    # Contains code block
    if "```" in query or re.search(r"`[^`]+`", query):
        score += 25

    # Contains math or formulas
    if re.search(r"[\$\\∑∫∂√∞≠≤≥]|(?:equation|formula|calculate|derivative|integral)", query, re.I):
        score += 20

    # Many retrieved chunks (complex context)
    if retrieved_chunk_count > 5:
        score += 15

    # Long conversation (accumulated context)
    if session_turn_count > 10:
        score += 10

    return score


def get_llm(
    query: str,
    retrieved_chunk_count: int = 0,
    session_turn_count: int = 0,
    local_model: str = _DEFAULT_LOCAL_MODEL,
    openai_model: str = _DEFAULT_OPENAI_MODEL,
    openai_api_key: str | None = None,
    complexity_threshold: int = _DEFAULT_THRESHOLD,
    force_openai: bool = False,
    ollama_base_url: str = _OLLAMA_BASE_URL,
) -> tuple[BaseChatModel, str]:
    """
    Return (llm_instance, routing_reason).

    routing_reason is a human-readable string explaining the decision,
    shown in the UI under each chat response.

    Examples:
      "ollama/llama3 (local)"
      "openai/gpt-4o — Ollama unavailable"
      "openai/gpt-4o — complexity score 75 ≥ threshold 60"
    """
    from langchain_openai import ChatOpenAI

    def _openai(reason: str) -> tuple[BaseChatModel, str]:
        if not openai_api_key:
            raise ValueError("OpenAI API key is required but not configured. Please add it in Settings.")
        llm = ChatOpenAI(model=openai_model, api_key=openai_api_key, temperature=0)
        return llm, f"openai/{openai_model} — {reason}"

    # Step 1: Ollama reachability
    if not is_ollama_running(ollama_base_url):
        return _openai("Ollama not running")

    # Step 2: Model pulled?
    if not _is_model_available(local_model, ollama_base_url):
        return _openai(f"model '{local_model}' not pulled in Ollama")

    # Step 3: Complexity scoring
    score = _complexity_score(query, retrieved_chunk_count, session_turn_count, force_openai)
    if score >= complexity_threshold:
        return _openai(f"complexity score {score} ≥ threshold {complexity_threshold}")

    # Route to local Ollama
    from langchain_community.chat_models import ChatOllama
    llm = ChatOllama(model=local_model, base_url=ollama_base_url, temperature=0)
    return llm, f"ollama/{local_model} (local) — score {score}"


def routing_is_local(routing_reason: str) -> bool:
    """Return True if the routing reason indicates a local model was used."""
    return routing_reason.startswith("ollama/")
