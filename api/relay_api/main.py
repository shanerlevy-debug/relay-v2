"""FastAPI application entrypoint.

Slim version of Powerloom's main.py — same skeleton (lifespan, CORS,
request-logging middleware, error handlers, modular routers) but without
the Powerloom-specific apparatus (schema version gate, super-admin host
isolation, rate limiter, deploy worker, workflow worker, ...). Add only
what we need; never carry forward "just in case."
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env before any module reads settings.
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

from relay_api.core.config import settings  # noqa: E402
from relay_api.core.errors import (  # noqa: E402
    register_error_handlers,
    request_logging_middleware,
)
from relay_api.core.logging import configure_logging, get_logger  # noqa: E402
from relay_api.routes import (  # noqa: E402
    agents,
    audit,
    auth,
    cma,
    health,
    invites,
    me,
    oauth_google,
    oauth_slack,
    users,
    workspace as workspace_routes,
)

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app_starting", env=settings.RELAY_ENV)
    yield
    log.info("app_stopping")


def create_app() -> FastAPI:
    """Application factory. Tests instantiate this directly."""
    app = FastAPI(
        title="Relay Control Plane",
        version="0.1.0",
        description="Multi-tenant Slack <-> Claude Managed Agents pop-up.",
        lifespan=lifespan,
    )

    # CORS — UI talks to API cross-origin in dev (localhost:3000 -> :8000).
    # In prod under relayed.live the UI and API may share an origin, in
    # which case allow_origins is a no-op but still safe.
    cors_origins = [settings.RELAY_APP_BASE_URL.rstrip("/")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Request logging — wraps every request in a request_id contextvar.
    app.add_middleware(BaseHTTPMiddleware, dispatch=request_logging_middleware)

    register_error_handlers(app)

    # Routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(oauth_slack.router)
    app.include_router(oauth_google.router)
    app.include_router(users.router)
    app.include_router(invites.router)
    app.include_router(agents.router)
    app.include_router(cma.router)
    app.include_router(workspace_routes.router)
    app.include_router(audit.router)

    log.info("app_created")
    return app


app = create_app()
