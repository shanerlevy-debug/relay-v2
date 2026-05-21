"""Cookie name + helpers for set/clear of the session cookie.

Centralized so the cookie attrs (HttpOnly, SameSite, Secure, Domain) are
consistent across set_cookie and delete_cookie — getting any of them
wrong on delete is a silent footgun (the cookie stays in the browser).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import Response

from relay_api.core.config import settings

COOKIE_NAME = "relay_session"


def set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    """Write the session cookie. Lifetime tracks the JWT's `exp`.

    `Secure=True` in non-dev requires HTTPS — make sure the prod nginx
    config terminates TLS so the browser will accept it.
    """
    domain = settings.RELAY_OAUTH_COOKIE_DOMAIN or None
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.RELAY_ENV != "dev",
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_MINUTES * 60,
        domain=domain,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Clear the session cookie. The browser only honors delete_cookie if
    the attrs match the original set_cookie — keep them in sync here."""
    domain = settings.RELAY_OAUTH_COOKIE_DOMAIN or None
    response.delete_cookie(
        key=COOKIE_NAME,
        domain=domain,
        path="/",
    )
