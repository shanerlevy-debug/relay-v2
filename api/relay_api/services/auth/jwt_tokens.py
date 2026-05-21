"""Issue and verify session JWTs.

The session token carries (user_id, workspace_id) — that's it. Workspace
membership is baked into the token so we don't have to look it up on every
request; if a user's workspace assignment ever changes (they wouldn't, in
v1's one-user-per-workspace model, but defensive), the token's `exp` upper-
bounds the staleness to JWT_ACCESS_TOKEN_MINUTES.

v1 uses HS256 with a single shared secret. Move to RS256 + KMS-backed keys
if/when we ever need to verify tokens in a separate process from where they
were issued. For one-box Lightsail that day is far away.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from relay_api.core.config import settings


class TokenError(Exception):
    """Raised on any JWT verify failure. Routes translate to 401."""


def issue_session_token(
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> tuple[str, datetime]:
    """Mint a signed session JWT. Returns (token, expires_at)."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_MINUTES)
    payload = {
        "sub": str(user_id),
        "ws": str(workspace_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def verify_session_token(token: str) -> dict:
    """Validate signature + claims. Returns the payload dict on success.

    Raises TokenError on expired, tampered, wrong-issuer, or otherwise
    invalid tokens. Don't leak which check failed — the route returns the
    same 401 for every case.
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
    except jwt.PyJWTError as e:
        raise TokenError(f"session token invalid: {e}") from e
