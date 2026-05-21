"""AES-256-GCM envelope encryption.

Free-function shape (not the Powerloom store-protocol pattern) — Relay
encrypts tokens on multiple unrelated tables (workspace_slack_installs,
workspace_anthropic_keys) and the caller is in the best position to
choose the column pair. Single 32-byte master key per deployment, in
env var `RELAY_MASTER_KEY_B64`.

Usage:

    from relay_api.services.envelope import encrypt, decrypt

    nonce, ct = encrypt(slack_bot_token, aad=install.id.bytes)
    install.bot_token_nonce = nonce
    install.bot_token_ct = ct

    plaintext = decrypt(install.bot_token_nonce, install.bot_token_ct,
                        aad=install.id.bytes)

The `aad` (additional authenticated data) binds the ciphertext to its
row. Swapping two rows' ciphertexts in Postgres invalidates both on
decrypt — that's the tamper-detection property. Pass the row's UUID
bytes as aad and you get it for free.
"""
from __future__ import annotations

import base64
import os
import threading

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from relay_api.core.config import settings

_MASTER_KEY_BYTES_LEN = 32  # AES-256
NONCE_LEN = 12  # GCM standard

_cache_lock = threading.Lock()
_cached_key: bytes | None = None


class EnvelopeError(Exception):
    """Raised when encrypt/decrypt or key resolution fails."""


def _load_master_key() -> bytes:
    """Resolve, validate, and cache the master key from settings."""
    global _cached_key
    if _cached_key is not None:
        return _cached_key

    with _cache_lock:
        if _cached_key is not None:
            return _cached_key

        b64 = settings.RELAY_MASTER_KEY_B64
        if not b64:
            raise EnvelopeError(
                "RELAY_MASTER_KEY_B64 is not set. Generate one with "
                "`python scripts/generate-master-key.py` and paste it into .env."
            )
        try:
            raw = base64.b64decode(b64, validate=True)
        except Exception as e:  # base64.binascii.Error and friends
            raise EnvelopeError(f"RELAY_MASTER_KEY_B64 is not valid base64: {e}") from e
        if len(raw) != _MASTER_KEY_BYTES_LEN:
            raise EnvelopeError(
                f"RELAY_MASTER_KEY_B64 decodes to {len(raw)} bytes; "
                f"expected {_MASTER_KEY_BYTES_LEN}"
            )
        _cached_key = raw

    return _cached_key


def reset_master_key_cache() -> None:
    """Tests call this after swapping settings. Production never calls it
    in steady state — the master key is immutable for the process."""
    global _cached_key
    with _cache_lock:
        _cached_key = None


def encrypt(plaintext: str, aad: bytes) -> tuple[bytes, bytes]:
    """Encrypt `plaintext` and return (nonce, ciphertext_with_tag).

    `aad` binds the ciphertext to its row. Use the row's UUID bytes.
    """
    aesgcm = AESGCM(_load_master_key())
    nonce = os.urandom(NONCE_LEN)
    try:
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
    except Exception as e:
        raise EnvelopeError(f"encrypt failed: {e}") from e
    return nonce, ct


def decrypt(nonce: bytes, ciphertext: bytes, aad: bytes) -> str:
    """Decrypt and return plaintext. Raises EnvelopeError on tamper / bad aad."""
    aesgcm = AESGCM(_load_master_key())
    try:
        pt = aesgcm.decrypt(bytes(nonce), bytes(ciphertext), aad)
    except Exception as e:
        # InvalidTag lands here. Don't help attackers distinguish bad-key
        # from bad-aad from bad-ciphertext via wording or timing.
        raise EnvelopeError("decrypt failed") from e
    return pt.decode("utf-8")
