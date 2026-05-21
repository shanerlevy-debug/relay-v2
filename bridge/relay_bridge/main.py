"""Bridge process entrypoint.

Multi-tenant Slack Socket Mode: one Bolt App that resolves per-workspace
bot tokens via an `authorize` callback. All installed workspaces deliver
events over the same App-Level Token (`RELAY_SLACK_APP_TOKEN`); the bot
tokens we send back to Slack's Web API come from `workspace_slack_installs`
decrypted just-in-time.

Run: `python -m relay_bridge.main`
"""
from __future__ import annotations

import sys

from dotenv import load_dotenv

# Load .env BEFORE any module reads settings.
load_dotenv()

from slack_bolt import App  # noqa: E402
from slack_bolt.adapter.socket_mode import SocketModeHandler  # noqa: E402
from slack_bolt.authorization.authorize_result import AuthorizeResult  # noqa: E402

from relay_api.core.config import settings  # noqa: E402
from relay_api.core.logging import configure_logging, get_logger  # noqa: E402
from relay_api.db.session import SessionLocal  # noqa: E402
from relay_api.services.slack_install import (  # noqa: E402
    decrypt_bot_token,
    find_by_team_id,
)

from relay_bridge.handlers import register_handlers  # noqa: E402

configure_logging()
log = get_logger("relay-bridge")


def authorize(
    enterprise_id: str | None,
    team_id: str | None,
    user_id: str | None,
    **_kwargs,
) -> AuthorizeResult | None:
    """Resolve per-workspace bot token at event time.

    Returns None for unknown / revoked workspaces — Bolt will skip the
    handler. We log so an operator can see if a stale workspace is
    delivering events (could indicate a half-revoked install).
    """
    if not team_id:
        log.warning("authorize.no_team_id")
        return None

    with SessionLocal() as db:
        install = find_by_team_id(db, slack_team_id=team_id)
        if install is None:
            log.info("authorize.unknown_team_id", team_id=team_id)
            return None
        bot_token = decrypt_bot_token(install)
        return AuthorizeResult(
            enterprise_id=enterprise_id,
            team_id=team_id,
            bot_token=bot_token,
            bot_user_id=install.bot_user_id,
        )


def create_app() -> App:
    """Build the Bolt App. Factored out for tests that want to register
    handlers without actually starting the Socket Mode connection."""
    if not settings.RELAY_SLACK_APP_TOKEN:
        log.error("config.missing_RELAY_SLACK_APP_TOKEN")
        raise SystemExit(
            "RELAY_SLACK_APP_TOKEN must be set (xapp-…). See bridge/.env.example."
        )
    app = App(authorize=authorize)
    register_handlers(app)
    return app


def main() -> int:
    log.info("bridge.starting")
    app = create_app()
    handler = SocketModeHandler(app, settings.RELAY_SLACK_APP_TOKEN)
    handler.start()
    return 0  # never reached in steady state — handler.start blocks


if __name__ == "__main__":
    sys.exit(main())
