"""Google OAuth 2.0 / OpenID Connect login provider.

Lifted from Powerloom's services/auth/oauth/google.py with the
Principal / ResolvedIdentity coupling stripped — Relay just needs
(email, display_name) back from the callback. The route handler decides
whether to log in an existing user or bootstrap a new workspace.
"""
from __future__ import annotations

import secrets as _py_secrets
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from relay_api.core.config import settings
from relay_api.services.oauth.base import (
    OAuthError,
    OAuthStartResult,
    generate_pkce_pair,
    serialize_state,
)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass(frozen=True)
class GoogleIdentity:
    """What we get back from Google's userinfo endpoint after a
    successful callback. The route handler turns this into either
    a login (existing user with matching email) or a workspace
    bootstrap (no existing user)."""

    sub: str           # Google's stable user ID (preferred over email for re-auth)
    email: str         # lowercase, verified-by-Google
    display_name: str  # full name from Google profile


class GoogleProvider:
    name = "google"

    def start_login(self, *, redirect_uri: str) -> OAuthStartResult:
        """Build Google's authorize URL + the signed state cookie.

        The state carries the PKCE verifier (so the callback can prove
        it knows the original secret) plus a nonce that goes both in
        the URL state and in the state cookie — equality check defends
        against state-fixation.
        """
        client_id = settings.OAUTH_GOOGLE_CLIENT_ID
        if not client_id:
            raise OAuthError("Google OAuth not configured", code="misconfigured")
        verifier, challenge = generate_pkce_pair()
        nonce = _py_secrets.token_urlsafe(24)
        state_cookie = serialize_state({
            "nonce": nonce,
            "verifier": verifier,
        })
        query = urllib.parse.urlencode({
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            # Force the consent screen so the email-verified claim is fresh.
            # Skip "offline" — we don't need a refresh token for login-only.
            "prompt": "select_account",
        })
        return OAuthStartResult(
            authorization_url=f"{AUTH_URL}?{query}",
            state_cookie_value=state_cookie,
        )

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        verifier: str,
    ) -> GoogleIdentity:
        """Exchange the authorization code for an access token, fetch
        userinfo, and return a typed identity.

        Raises OAuthError on any failure including unverified emails —
        we never log in a user whose Google account hasn't verified
        their address.
        """
        client_id = settings.OAUTH_GOOGLE_CLIENT_ID
        client_secret = settings.OAUTH_GOOGLE_CLIENT_SECRET
        if not client_id or not client_secret:
            raise OAuthError("Google OAuth not configured", code="misconfigured")

        async with httpx.AsyncClient(timeout=10.0) as client:
            tok_resp = await client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
            if tok_resp.status_code != 200:
                raise OAuthError(
                    f"google token exchange http {tok_resp.status_code}",
                    code="exchange_failed",
                )
            tokens = tok_resp.json()
            access_token = tokens.get("access_token")
            if not access_token:
                raise OAuthError(
                    "google token response missing access_token",
                    code="exchange_failed",
                )

            ui_resp = await client.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if ui_resp.status_code != 200:
                raise OAuthError(
                    f"google userinfo http {ui_resp.status_code}",
                    code="userinfo_failed",
                )
            info = ui_resp.json()

        sub = str(info.get("sub") or "")
        email = str(info.get("email") or "").strip().lower()
        if not sub or not email:
            raise OAuthError(
                "google userinfo missing sub or email",
                code="userinfo_failed",
            )
        if not info.get("email_verified", False):
            # Reject unverified Google accounts. The user can still sign
            # up with email + password if they want — but we won't let
            # them log in via Google until Google says the email is
            # actually theirs.
            raise OAuthError(
                "your Google account has not verified this email",
                code="email_not_verified",
            )
        display_name = str(info.get("name") or email.split("@")[0])
        return GoogleIdentity(sub=sub, email=email, display_name=display_name)
