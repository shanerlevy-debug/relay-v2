"""Health check — used by uptime monitors and the load balancer.

Returns 200 with a structured body so the operator (or a probe) can
distinguish "API up" from "API up and DB reachable" at a glance.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from relay_api import __version__
from relay_api.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Returns 200 always; the `db` field tells you if Postgres is reachable.

    Intentionally never 5xx on DB failure — the API is still "up" even when
    Postgres is down (login + agent reads degrade, but webhook ingest and
    health probes shouldn't take down the box). Operators wire the alerter
    to `db == "down"` rather than relying on HTTP status.
    """
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"

    return {
        "status": "ok",
        "version": __version__,
        "db": db_status,
    }
