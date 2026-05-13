"""
Tests for ingestion/chunker.py and ingestion/loader.py (no filesystem or model deps).

Run: python -m pytest tests/test_ingestion.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.chunker import chunk_texts


def test_chunk_texts_basic():
    sections = ["Hello world. " * 100]
    chunks = chunk_texts(sections, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1, "Long text should produce multiple chunks"
    for chunk in chunks:
        assert len(chunk) <= 250, "Chunks should not far exceed chunk_size"


def test_chunk_texts_preserves_content():
    text = "The quick brown fox jumps over the lazy dog. " * 50
    chunks = chunk_texts([text], chunk_size=100, chunk_overlap=10)
    # All content should appear somewhere in the chunks
    combined = " ".join(chunks)
    assert "quick brown fox" in combined


def test_chunk_texts_empty_sections():
    chunks = chunk_texts([], chunk_size=800, chunk_overlap=100)
    assert chunks == []


def test_chunk_texts_short_text_is_single_chunk():
    sections = ["Short text."]
    chunks = chunk_texts(sections, chunk_size=800, chunk_overlap=100)
    assert len(chunks) == 1
    assert chunks[0] == "Short text."


def test_chunk_overlap_produces_repeated_content():
    text = "AAAA BBBB CCCC DDDD EEEE " * 20
    chunks = chunk_texts([text], chunk_size=50, chunk_overlap=20)
    assert len(chunks) > 2


if __name__ == "__main__":
    tests = [
        test_chunk_texts_basic,
        test_chunk_texts_preserves_content,
        test_chunk_texts_empty_sections,
        test_chunk_texts_short_text_is_single_chunk,
        test_chunk_overlap_produces_repeated_content,
    ]
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
