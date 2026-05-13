"""
Tests for core/crypto.py

Run: python -m pytest tests/test_crypto.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.crypto import (
    decrypt_text,
    encrypt_text,
    generate_key_and_phrase,
    get_fernet,
    key_fingerprint,
    restore_key_from_phrase,
)


def test_generate_key_returns_bytes_and_12_words():
    key_bytes, phrase = generate_key_and_phrase()
    assert isinstance(key_bytes, bytes)
    assert len(key_bytes) == 44  # Fernet base64url key is 44 chars
    words = phrase.split()
    assert len(words) == 12


def test_key_is_deterministic_from_phrase():
    key1, phrase = generate_key_and_phrase()
    key2 = restore_key_from_phrase(phrase)
    assert key1 == key2, "Same phrase must produce same key"


def test_encrypt_decrypt_roundtrip():
    key_bytes, _ = generate_key_and_phrase()
    fernet = get_fernet(key_bytes)
    original = "This is my private document text. It should be readable after decryption."
    token = encrypt_text(fernet, original)
    assert token != original
    recovered = decrypt_text(fernet, token)
    assert recovered == original


def test_wrong_key_raises():
    key1, _ = generate_key_and_phrase()
    key2, _ = generate_key_and_phrase()
    fernet1 = get_fernet(key1)
    fernet2 = get_fernet(key2)
    token = encrypt_text(fernet1, "secret text")
    try:
        decrypt_text(fernet2, token)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_fingerprint_is_8_hex_chars():
    key_bytes, _ = generate_key_and_phrase()
    fp = key_fingerprint(key_bytes)
    assert len(fp) == 8
    assert all(c in "0123456789abcdef" for c in fp)


def test_restore_from_phrase_invalid_word_count():
    try:
        restore_key_from_phrase("only five words here now")
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "12 words" in str(e)


def test_restore_from_phrase_unknown_words():
    try:
        restore_key_from_phrase("zzz zzz zzz zzz zzz zzz zzz zzz zzz zzz zzz zzz")
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "Unknown words" in str(e)


if __name__ == "__main__":
    tests = [
        test_generate_key_returns_bytes_and_12_words,
        test_key_is_deterministic_from_phrase,
        test_encrypt_decrypt_roundtrip,
        test_wrong_key_raises,
        test_fingerprint_is_8_hex_chars,
        test_restore_from_phrase_invalid_word_count,
        test_restore_from_phrase_unknown_words,
    ]
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
