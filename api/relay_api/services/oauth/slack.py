"""Slack OAuth 2.0 install — multi-tenant workspace install flow.

Adapted from Powerloom's services/auth/oauth/slack.py. Dropped:
- User-scope (xoxp-…) request path — Relay only needs bot tokens
- Refresh-token plumbing — not needed for v1
- PKCE — Slack doesn't use it

Slack endpoints (per https://docs.slack.dev/authentication/installing-with-oauth/):
    authorize:  https://slack.com/oauth/v2/authorize
    exchange:   https://slack.com/api/oauth.v2.access
    revoke:     https://slack.com/api/auth.revoke

Authorization request shape:
    GET /oauth/v2/authorize?
        client_id=...
        &scope=<bot-scope-csv>
        &redirect_uri=https://relayed.live/api/oauth/slack/callback
        &state=<random>     ← signed cookie validates this

Response body shape (success):
    {
        "ok": true,
        "access_token": "xoxb-…",         ← bot token (we persist this, encrypted)
        "token_type": "bot",
        "scope": "chat:write,...",
        "bot_user_id": "U…",
        "app_id": "A…",
        "team": {"id":"T…","name":"…"},
        "enterprise": {"id":"E…","name":"…"} | null,
        "authed_user": {"id":"U…","scope":"...","access_token":"xoxp-…",...}
    }
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
    serialize_state,
)

AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
TOKEN_EXCHANGE_URL = "https://slack.com/api/oauth.v2.access"
REVOKE_URL = "https://slack.com/api/auth.revoke"


# Default bot scopes — matches what Relay v1 actually needs at runtime.
# Mirrors slack-app-manifest.yaml in the v1 bridge.
DEFAULT_BOT_SCOPES: tuple[str, ...] = (
    "app_mentions:read",
    "chat:write",
    "chat:write.public",
    "channels:history",
    "im:history",
    "im:write",
    "commands",
)


def _configured_bot_scopes() -> tuple[str, ...]:
    raw = settings.OAUTH_SLACK_BOT_SCOPES
    if not raw:
        return DEFAULT_BOT_SCOPES
    scopes = tuple(s.strip() for s in raw.replace(",", " ").split() if s.strip())
    return scopes or DEFAULT_BOT_SCOPES


@dataclass(frozen=True)
class SlackInstallExchange:
    """Structured form of the relevant subset of Slack's `oauth.v2.access`
    response. The full dict is also returned (as `raw`) for the service
    layer to persist whatever shape it wants without this DTO needing every
    field."""

    raw: dict[str, Any]
    bot_token: str
    bot_user_id: str
    app_id: str
    bot_scopes_granted: list[str]
    team_id: str
    team_name: str
    enterprise_id: str | None
    enterprise_name: str | None


class SlackProvider:
    """Slack OAuth install. Stateless — one instance per process is fine."""

    name = "slack"

    def start_install(
        self,
        *,
        redirect_uri: str,
        workspace_id: str,
        user_id: str,
        bot_scopes: tuple[str, ...] | None = None,
    ) -> OAuthStartResult:
        """Build the authorize URL + the signed state cookie.

        `workspace_id` and `user_id` are carried in the state cookie so the
        callback knows which workspace owns this install and who's recording it.
        """
        client_id = settings.OAUTH_SLACK_CLIENT_ID
        if not client_id:
            raise OAuthError("Slack OAuth not configured", code="misconfigured")

        # Random nonce in the state — the cookie's signature is the real
        # CSRF defense, but the nonce makes the URL non-replayable.
        nonce = _py_secrets.token_urlsafe(24)
        state_cookie = serialize_state({
            "nonce": nonce,
            "workspace_id": workspace_id,
            "user_id": user_id,
        })

        effective_scopes = bot_scopes or _configured_bot_scopes()
        query = urllib.parse.urlencode({
            "client_id": client_id,
            "scope": ",".join(effective_scopes),
            "redirect_uri": redirect_uri,
            "state": nonce,
        })
        return OAuthStartResult(
            authorization_url=f"{AUTHORIZE_URL}?{query}",
            state_cookie_value=state_cookie,
        )

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
    ) -> SlackInstallExchange:
        """Exchange the authorization code for a bot install via oauth.v2.access.

        Raises OAuthError on any failure: HTTP error, `ok: false` body,
        malformed response. Logs are deliberately terse to avoid leaking tokens
        into log aggregators.
        """
        client_id = settings.OAUTH_SLACK_CLIENT_ID
        client_secret = settings.OAUTH_SLACK_CLIENT_SECRET
        if not client_id or not client_secret:
            raise OAuthError("Slack OAuth not configured", code="misconfigured")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                TOKEN_EXCHANGE_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

        if resp.status_code != 200:
            raise OAuthError(
                f"slack token exchange http {resp.status_code}",
                code="exchange_failed",
            )

        body = resp.json()
        if not body.get("ok"):
            raise OAuthError(
                f"slack token exchange returned ok=false: {body.get('error')!r}",
                code="exchange_failed",
            )

        # Validate the required shape — Slack's docs guarantee these on success.
        bot_token = body.get("access_token")
        if not bot_token or not str(bot_token).startswith("xoxb-"):
            raise OAuthError(
                "slack response missing or malformed bot access_token",
                code="exchange_failed",
            )
        bot_user_id = body.get("bot_user_id")
        app_id = body.get("app_id")
        team = body.get("team") or {}
        enterprise = body.get("enterprise") or None
        scopes_csv = body.get("scope") or ""
        if not bot_user_id or not app_id or not team.get("id"):
            raise OAuthError(
                "slack response missing required identifiers",
                code="exchange_failed",
            )

        return SlackInstallExchange(
            raw=body,
            bot_token=bot_token,
            bot_user_id=bot_user_id,
            app_id=app_id,
            bot_scopes_granted=[
                s.strip() for s in scopes_csv.split(",") if s.strip()
            ],
            team_id=team["id"],
            team_name=team.get("name") or team["id"],
            enterprise_id=(enterprise or {}).get("id") if enterprise else None,
            enterprise_name=(enterprise or {}).get("name") if enterprise else None,
        )

    async def revoke(self, *, bot_token: str) -> None:
        """Best-effort revocation of a bot token via auth.revoke.

        Called when a user uninstalls. Slack errors here are logged but not
        raised — the workspace_slack_installs row is the source of truth, and
        marking it revoked is what matters. If Slack's side gets out of sync,
        the next install will silently mint a fresh token anyway.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.post(
                    REVOKE_URL,
                    data={"token": bot_token},
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError:
                # Intentional swallow — see docstring.
                pass
