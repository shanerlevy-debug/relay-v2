"""Transactional email — pluggable provider behind a single send() API.

Two providers in v1:
  console  — prints to stdout (dev default; useful before Resend is wired)
  resend   — POSTs to api.resend.com via the documented REST API

The `RELAY_EMAIL_PROVIDER` setting picks which one runs. Resend needs
`RESEND_API_KEY` set or it falls back to console with a warning.

Email body is HTML — we don't ship a templating engine, just a small
helper that renders the invite email's button + footer. Keep templates
inline; if we grow past two emails worth, lift to a templates dir.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from relay_api.core.config import settings
from relay_api.core.logging import get_logger

log = get_logger(__name__)


class EmailError(Exception):
    """Raised on send failure. Routes should map to a 502/500 with a
    user-visible 'we couldn't email the invite, here's the URL to share
    manually' fallback rather than rolling back the invite row."""


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str  # plain-text fallback


class _Provider(Protocol):
    def send(self, msg: EmailMessage) -> None: ...


class _ConsoleProvider:
    def send(self, msg: EmailMessage) -> None:
        log.info(
            "email.console_send",
            to=msg.to,
            subject=msg.subject,
            preview=msg.text[:120],
        )


class _ResendProvider:
    """Resend's REST API at https://api.resend.com/emails — see
    https://resend.com/docs/api-reference/emails/send-email.
    """

    def __init__(self, api_key: str, from_addr: str, from_name: str):
        self.api_key = api_key
        self.from_addr = from_addr
        self.from_name = from_name

    def send(self, msg: EmailMessage) -> None:
        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{self.from_name} <{self.from_addr}>",
                    "to": [msg.to],
                    "subject": msg.subject,
                    "html": msg.html,
                    "text": msg.text,
                },
                timeout=10.0,
            )
        except httpx.HTTPError as e:
            raise EmailError(f"resend network error: {e}") from e
        if resp.status_code >= 300:
            raise EmailError(
                f"resend http {resp.status_code}: {resp.text[:200]}"
            )


def _pick_provider() -> _Provider:
    name = (settings.RELAY_EMAIL_PROVIDER or "console").lower()
    if name == "resend":
        if not settings.RESEND_API_KEY:
            log.warning(
                "email.resend_no_key_falling_back_to_console",
            )
            return _ConsoleProvider()
        return _ResendProvider(
            api_key=settings.RESEND_API_KEY,
            from_addr=settings.RELAY_EMAIL_FROM,
            from_name=settings.RELAY_EMAIL_FROM_NAME,
        )
    return _ConsoleProvider()


# Lazily initialized — settings can be swapped in tests via the
# reset_provider() hook.
_provider: _Provider | None = None


def _get_provider() -> _Provider:
    global _provider
    if _provider is None:
        _provider = _pick_provider()
    return _provider


def reset_provider() -> None:
    """Tests call this after swapping settings."""
    global _provider
    _provider = None


def send(msg: EmailMessage) -> None:
    """Send a single email. Raises EmailError on failure — caller decides
    whether to surface to the user or fall back gracefully."""
    _get_provider().send(msg)


# ---------------------------------------------------------------------------
# Template helpers — inline HTML, small set.
# ---------------------------------------------------------------------------


def render_invite_email(
    *,
    workspace_name: str,
    invite_url: str,
    inviter_email: str | None = None,
) -> tuple[str, str]:
    """Build (html, text) bodies for the Sign-in-with-Slack invite email.

    The CTA button points at the slack-signin /start route with the
    invite token in the query string — Slack OIDC flow runs, callback
    consumes the invite and creates the Relay user.
    """
    inviter = (
        f"{inviter_email} invited you to" if inviter_email else "You've been invited to"
    )
    text = (
        f"{inviter} {workspace_name} on Relay.\n\n"
        f"Click the link below to sign in with your Slack account. "
        f"You'll be set up as a workspace member automatically.\n\n"
        f"{invite_url}\n\n"
        f"If you weren't expecting this, you can ignore the email.\n\n"
        f"— Relay (relayed.live)"
    )
    html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f8f7f3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1f1f1f;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f7f3;padding:40px 16px;">
    <tr><td align="center">
      <table width="100%" style="max-width:520px;background:#ffffff;border:1px solid #e6e4dd;border-radius:8px;padding:32px;">
        <tr><td>
          <div style="font-size:14px;color:#838a95;text-transform:uppercase;letter-spacing:0.08em;font-family:'JetBrains Mono',ui-monospace,monospace;">relay</div>
          <h1 style="font-size:22px;font-weight:600;margin:18px 0 12px;letter-spacing:-0.015em;">
            Join {_h(workspace_name)} on Relay
          </h1>
          <p style="font-size:15px;line-height:1.55;color:#4a515c;margin:0 0 24px;">
            {_h(inviter)} <strong>{_h(workspace_name)}</strong>. Click below to
            sign in with your Slack account — we'll set you up as a workspace
            member automatically. No password to remember.
          </p>
          <table cellpadding="0" cellspacing="0" style="margin:8px 0 24px;">
            <tr><td style="border-radius:6px;background:#4A154B;">
              <a href="{_h(invite_url)}" style="display:inline-block;padding:12px 20px;color:#ffffff;text-decoration:none;font-weight:500;font-size:14px;border-radius:6px;">
                Sign in with Slack
              </a>
            </td></tr>
          </table>
          <p style="font-size:13px;line-height:1.55;color:#838a95;margin:24px 0 0;border-top:1px solid #f0eee7;padding-top:18px;">
            If you weren't expecting this email, you can safely ignore it —
            the invite link won't do anything until you click it.
          </p>
          <p style="font-size:11px;color:#a0a5ac;margin:14px 0 0;font-family:'JetBrains Mono',ui-monospace,monospace;">
            relay · relayed.live
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
    return html, text


def _h(s: str) -> str:
    """Bare-minimum HTML escape — sufficient for the small set of values
    we interpolate (workspace name, email, URL). Switch to MarkupSafe if
    we grow past trivial templates."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
