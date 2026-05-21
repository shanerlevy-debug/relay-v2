"""Smoke test for the envelope encryption primitive.

Uses a fixed dev master key set via env var so the test is pure-Python
(no Secrets Manager, no Postgres).
"""
from __future__ import annotations

import base64
import os
import uuid

import pytest

# Set a deterministic master key BEFORE the envelope module loads it.
os.environ.setdefault(
    "RELAY_MASTER_KEY_B64",
    base64.b64encode(b"\x00" * 32).decode("ascii"),
)

from relay_api.services.envelope import (  # noqa: E402
    EnvelopeError,
    decrypt,
    encrypt,
    reset_master_key_cache,
)


def test_roundtrip() -> None:
    reset_master_key_cache()
    aad = uuid.uuid4().bytes
    nonce, ct = encrypt("xoxb-secret-token", aad)
    assert len(nonce) == 12
    assert ct != b"xoxb-secret-token"
    out = decrypt(nonce, ct, aad)
    assert out == "xoxb-secret-token"


def test_swap_aad_fails() -> None:
    """AAD binds ciphertext to a specific row — swapping rows must fail."""
    reset_master_key_cache()
    aad_a = uuid.uuid4().bytes
    aad_b = uuid.uuid4().bytes
    nonce, ct = encrypt("secret", aad_a)
    with pytest.raises(EnvelopeError):
        decrypt(nonce, ct, aad_b)


def test_tampered_ciphertext_fails() -> None:
    reset_master_key_cache()
    aad = uuid.uuid4().bytes
    nonce, ct = encrypt("secret", aad)
    # Flip a byte
    tampered = bytearray(ct)
    tampered[0] ^= 0xFF
    with pytest.raises(EnvelopeError):
        decrypt(nonce, bytes(tampered), aad)
