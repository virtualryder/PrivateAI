"""
Tests for core/model_router.py (logic only — no live Ollama or OpenAI required).

Run: python -m pytest tests/test_router.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.model_router import _complexity_score, routing_is_local


def test_short_simple_query_scores_low():
    score = _complexity_score("What did I write in my notes?", 2, 0)
    assert score < 40


def test_long_query_adds_20():
    long_q = " ".join(["word"] * 55)
    score = _complexity_score(long_q, 0, 0)
    assert score >= 20


def test_code_block_adds_25():
    query = "Explain this code: ```python\nprint('hello')\n```"
    score = _complexity_score(query, 0, 0)
    assert score >= 25


def test_math_adds_20():
    query = "Solve this equation: ∑x² + derivative"
    score = _complexity_score(query, 0, 0)
    assert score >= 20


def test_many_chunks_adds_15():
    score = _complexity_score("simple query", 6, 0)
    assert score >= 15


def test_long_session_adds_10():
    score = _complexity_score("simple query", 0, 15)
    assert score >= 10


def test_force_openai_returns_100():
    score = _complexity_score("simple", 0, 0, force_openai=True)
    assert score == 100


def test_routing_is_local_true():
    assert routing_is_local("ollama/llama3 (local) — score 30") is True


def test_routing_is_local_false():
    assert routing_is_local("openai/gpt-4o — Ollama not running") is False


if __name__ == "__main__":
    tests = [
        test_short_simple_query_scores_low,
        test_long_query_adds_20,
        test_code_block_adds_25,
        test_math_adds_20,
        test_many_chunks_adds_15,
        test_long_session_adds_10,
        test_force_openai_returns_100,
        test_routing_is_local_true,
        test_routing_is_local_false,
    ]
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
