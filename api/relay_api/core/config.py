"""Runtime configuration loaded from environment.

Slim version of Powerloom's Settings — only the surface Relay actually
uses. Add fields as features land; never carry settings forward "just
in case" — they grow without bound otherwise.

Settings are read once at module import (`settings = Settings()`) and
accessed as `settings.FOO`. Nothing secret should be hard-coded.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Runtime flavor ----
    RELAY_ENV: str = "dev"
    RELAY_LOG_LEVEL: str = "INFO"

    # ---- Database ----
    # psycopg 3 driver (not psycopg2).
    DATABASE_URL: str = (
        "postgresql+psycopg://relay:relay_dev@localhost:5432/relay_dev"
    )

    # ---- Public URLs ----
    # Drive OAuth callback URLs + cookie scoping. In dev these point at
    # localhost; in prod both should be https://relayed.live.
    RELAY_APP_BASE_URL: str = "http://localhost:3000"
    RELAY_API_PUBLIC_URL: str = "http://localhost:8000"
    # Empty string = no Domain attr on cookies (correct for single-host
    # deploys where the API + UI share an origin). Set to ".relayed.live"
    # only if subdomain-splitting api from app later.
    RELAY_OAUTH_COOKIE_DOMAIN: str = ""

    # ---- Auth (cookie session) ----
    # HS256 for v1; rotate to RS256 with KMS-backed keys if/when needed.
    # DO NOT use the default in anything but local dev. ≥32 bytes (256 bits)
    # per RFC 7518 §3.2 to silence pyjwt's InsecureKeyLength warning.
    JWT_SECRET: str = "dev-secret-do-not-use-in-prod-12345678901234567890"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "relay-api"
    JWT_AUDIENCE: str = "relay-app"
    JWT_ACCESS_TOKEN_MINUTES: int = 60
    JWT_REFRESH_TOKEN_DAYS: int = 7

    # ---- Envelope encryption master key ----
    # 32 raw bytes, base64-encoded. Generate via scripts/generate-master-key.py.
    # In prod: lives at /etc/relay/master.key (chmod 0400) and is loaded into
    # this env var by the systemd unit's EnvironmentFile directive.
    RELAY_MASTER_KEY_B64: str | None = None

    # ---- Slack OAuth (multi-tenant install) ----
    # One Slack App per Relay deployment; per-workspace bot tokens are
    # encrypted into workspace_slack_installs after `oauth.v2.access`.
    OAUTH_SLACK_CLIENT_ID: str | None = None
    OAUTH_SLACK_CLIENT_SECRET: str | None = None
    OAUTH_SLACK_BOT_SCOPES: str = (
        "app_mentions:read chat:write chat:write.public "
        "channels:history im:history im:write commands"
    )

    # ---- Google OAuth (login + signup) ----
    # OAuth 2.0 Web Application client from console.cloud.google.com.
    # Redirect URI must be set to {RELAY_API_PUBLIC_URL}/api/oauth/google/callback.
    # Empty = "Continue with Google" buttons render but the /start route
    # returns 500 misconfigured.
    OAUTH_GOOGLE_CLIENT_ID: str | None = None
    OAUTH_GOOGLE_CLIENT_SECRET: str | None = None

    # ---- Transactional email ----
    # "console" prints to stdout (dev). "ses" calls AWS SES (prod, once
    # the relayed.live domain is DNS-verified).
    RELAY_EMAIL_PROVIDER: str = "console"
    RELAY_EMAIL_FROM: str = "no-reply@relayed.live"
    RELAY_EMAIL_FROM_NAME: str = "Relay"

    # ---- Plan limits (the 25/25 ceiling) ----
    RELAY_USERS_PER_WORKSPACE: int = 25
    RELAY_AGENTS_PER_WORKSPACE: int = 25

    # ---- Bridge process (Socket Mode + CMA) ----
    # App-Level Token for Slack Socket Mode. One per Slack App regardless
    # of how many workspaces install it. The per-workspace bot tokens
    # (xoxb-...) come from workspace_slack_installs at event time.
    RELAY_SLACK_APP_TOKEN: str | None = None

    # Slash command name. Must match the Slack App manifest's slash_commands entry.
    RELAY_SLACK_SLASH_COMMAND: str = "/relay"

    # Debug — when true, the bridge logs every CMA stream event type.
    # Useful for SDK-shape discovery; turn off in steady state.
    RELAY_BRIDGE_LOG_EVENT_TYPES: bool = False


settings = Settings()
