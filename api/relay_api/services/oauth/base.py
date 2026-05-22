"""Signed-state-cookie helpers for OAuth flows.

The "state" parameter Slack expects round-trips through the browser. Sending
it in the URL would let an attacker forge it; instead we store it in a
signed cookie, and the bytes Slack actually sees are random — Slack just
echoes them back. The real verification happens against the cookie, which
itsdangerous signs with our JWT_SECRET.

State payload carries the install context (workspace_id, user_id, fresh
random nonce). The callback decodes it to know which workspace owns this
install and who's recording the install.
"""
from __future__ import annotations

import base64
import hashlib
import secrets as _py_secrets
from dataclasses import dataclass
from typing import Any

from itsdangerous import BadSignature, URLSafeSerializer

from relay_api.core.config import settings

OAUTH_STATE_COOKIE = "relay_oauth_state"

# Salted serializer — even if JWT_SECRET were ever shared with another
# subsystem (it isn't today), the salt guarantees those tokens can't be
# confused with session JWTs.
_STATE_SERIALIZER = URLSafeSerializer(settings.JWT_SECRET, salt="relay-oauth-state")


class OAuthError(Exception):
    """Expected OAuth-flow failures. The `code` field is what the UI/route
    branches on; the message is human-readable."""

    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class OAuthStartResult:
    """What `start_install` returns. The route puts `state_cookie_value`
    into a cookie and redirects to `authorization_url`."""

    authorization_url: str
    state_cookie_value: str


def serialize_state(payload: dict[str, Any]) -> str:
    """Sign + URL-safe-encode the state payload. Returns the cookie value."""
    return _STATE_SERIALIZER.dumps(payload)


def deserialize_state(token: str) -> dict[str, Any]:
    """Validate signature and return the payload. Raises OAuthError on
    tamper / wrong-salt / corrupt cookie."""
    try:
        return _STATE_SERIALIZER.loads(token)
    except BadSignature as e:
        raise OAuthError("invalid OAuth state cookie", code="bad_state") from e


def generate_pkce_pair() -> tuple[str, str]:
    """Return (verifier, S256 challenge) for an OAuth PKCE handshake.

    RFC 7636 §4.1: verifier is 43–128 chars of unreserved URL-safe characters.
    Challenge = base64-url(sha256(verifier)) with padding stripped.
    """
    verifier = _py_secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge
