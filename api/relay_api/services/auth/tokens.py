"""One-shot URL tokens — for invites, password reset, email verification.

Adapted from Powerloom's services/auth/tokens.py. Returns raw bytes (not
hex) so callers can store them in LargeBinary columns directly without an
encoding round-trip.

Token shape:
    raw    = 32 bytes of `secrets.token_urlsafe(32)` → 43-char URL-safe string
    hash   = sha256(raw).digest()  (32 raw bytes)

We only ever write the SHA-256 to the DB. The raw token is emitted to the
user exactly once, embedded in the outgoing email URL. A DB leak never
yields a working token.

Consumption is single-use: the row's `accepted_at` is stamped on accept.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

# Token lifetimes
INVITE_TTL = timedelta(days=7)
EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(hours=1)

_RAW_TOKEN_BYTES = 32


def mint_token() -> tuple[str, bytes]:
    """Return (raw_token, hash). Raw goes in the email body; hash goes in
    the DB column (LargeBinary(32))."""
    raw = secrets.token_urlsafe(_RAW_TOKEN_BYTES)
    return raw, hash_token(raw)


def hash_token(raw: str) -> bytes:
    """SHA-256 digest. 32 raw bytes — matches LargeBinary(32) column width."""
    return hashlib.sha256(raw.encode("utf-8")).digest()


def expires_at(ttl: timedelta) -> datetime:
    """Helper for route handlers — `datetime.now(UTC) + ttl`."""
    return datetime.now(UTC) + ttl


def is_expired(expires: datetime, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return now >= expires
