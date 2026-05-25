"""Sign in with Slack — OpenID Connect.

Same Slack App as the bot install (services/oauth/slack.py), different
endpoints + scopes. Slack's OIDC layer:

  authorize:  https://slack.com/openid/connect/authorize
  token:      https://slack.com/api/openid.connect.token
  userinfo:   https://slack.com/api/openid.connect.userInfo

Scopes are USER scopes (openid email profile), passed as `user_scope`
in the authorize URL (NOT `scope`, which is reserved for bot scopes).

Returns a SlackSignInIdentity with:
  team_id   — Slack workspace id (matches WorkspaceSlackInstall.slack_team_id)
  user_id   — Slack user id within that team
  email     — verified by Slack at workspace-join time
  name      — display name (best-effort)

Used by routes/oauth_slack_signin.py to authenticate (or auto-create)
a Relay user account bound to that Slack identity.
"""
from __future__ import annotations

import secrets as _py_secrets
import urllib.parse
from dataclasses import dataclass

import httpx

from relay_api.core.config import settings
from relay_api.services.oauth.base import (
    OAuthError,
    OAuthStartResult,
    serialize_state,
)

AUTH_URL = "https://slack.com/openid/connect/authorize"
TOKEN_URL = "https://slack.com/api/openid.connect.token"
USERINFO_URL = "https://slack.com/api/openid.connect.userInfo"


@dataclass(frozen=True)
class SlackSignInIdentity:
    """What Slack OIDC returns about the signed-in user. Slack-verified —
    the email is the address Slack itself validated at workspace-join
    time, and the team_id is unforgeable."""

    team_id: str
    user_id: str
    email: str
    name: str | None


class SlackSignInProvider:
    """Stateless OIDC client. One instance per process is fine."""

    name = "slack-signin"

    def start_signin(
        self,
        *,
        redirect_uri: str,
        extra_state: dict | None = None,
    ) -> OAuthStartResult:
        """Build Slack's OIDC authorize URL + the signed state cookie.

        `extra_state` carries flow-specific bits the callback will need
        (e.g. invite_token, link_to_user_id) — opaque to the OIDC layer.
        """
        client_id = settings.OAUTH_SLACK_CLIENT_ID
        if not client_id:
            raise OAuthError(
                "Slack OAuth not configured", code="misconfigured"
            )
        nonce = _py_secrets.token_urlsafe(24)
        state_payload = {"nonce": nonce}
        if extra_state:
            state_payload.update(extra_state)
        state_cookie = serialize_state(state_payload)
        # Slack OIDC takes `scope` (the openid trio); the legacy bot
        # install URL uses `user_scope`/`scope` for separate token types.
        # For OIDC sign-in, we use `scope` for the OIDC scopes.
        query = urllib.parse.urlencode({
            "response_type": "code",
            "client_id": client_id,
            "scope": settings.OAUTH_SLACK_USER_SCOPES,
            "redirect_uri": redirect_uri,
            "state": nonce,
            # nonce in the OIDC sense (separate from CSRF nonce above) —
            # bound into the id_token. We don't currently verify the
            # id_token signature locally; we trust the token-exchange
            # round-trip + userinfo lookup. Could harden later.
            "nonce": nonce,
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
    ) -> SlackSignInIdentity:
        """Exchange the auth code for tokens, fetch userinfo, return
        a typed identity.

        Slack's openid.connect.token returns an `access_token` (user
        token) that's valid against openid.connect.userInfo. We don't
        retain the access_token — the userinfo response is everything
        we need for binding."""
        client_id = settings.OAUTH_SLACK_CLIENT_ID
        client_secret = settings.OAUTH_SLACK_CLIENT_SECRET
        if not client_id or not client_secret:
            raise OAuthError(
                "Slack OAuth not configured", code="misconfigured"
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            tok_resp = await client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            if tok_resp.status_code != 200:
                raise OAuthError(
                    f"slack OIDC token http {tok_resp.status_code}",
                    code="exchange_failed",
                )
            tokens = tok_resp.json()
            if not tokens.get("ok", True):
                # Slack returns ok=false on some errors; mirror handling.
                raise OAuthError(
                    f"slack OIDC token returned {tokens.get('error')!r}",
                    code="exchange_failed",
                )
            access_token = tokens.get("access_token")
            if not access_token:
                raise OAuthError(
                    "slack OIDC token response missing access_token",
                    code="exchange_failed",
                )

            ui_resp = await client.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if ui_resp.status_code != 200:
                raise OAuthError(
                    f"slack OIDC userinfo http {ui_resp.status_code}",
                    code="userinfo_failed",
                )
            info = ui_resp.json()

        if not info.get("ok", True):
            raise OAuthError(
                f"slack OIDC userinfo ok=false: {info.get('error')!r}",
                code="userinfo_failed",
            )

        # Slack's OIDC userinfo shape:
        #   "sub":                  "Tteamid-Uuserid"
        #   "email":                "alice@bigco.com"
        #   "email_verified":       true
        #   "name":                 "Alice Smith"
        #   "https://slack.com/team_id": "T07..."
        #   "https://slack.com/user_id": "U07..."
        team_id = info.get("https://slack.com/team_id") or ""
        user_id = info.get("https://slack.com/user_id") or ""
        email = str(info.get("email") or "").strip().lower()
        if not team_id or not user_id or not email:
            raise OAuthError(
                "slack OIDC userinfo missing team_id / user_id / email",
                code="userinfo_failed",
            )
        if not info.get("email_verified", True):
            # Slack rarely sets this to False; defend anyway.
            raise OAuthError(
                "your Slack account hasn't verified this email",
                code="email_not_verified",
            )
        name = info.get("name") or None
        return SlackSignInIdentity(
            team_id=team_id,
            user_id=user_id,
            email=email,
            name=name,
        )
