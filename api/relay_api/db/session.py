"""SQLAlchemy engine + session factory."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from relay_api.core.config import settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models.

    `type_annotation_map` makes every `Mapped[datetime]` field land as a
    TIMESTAMPTZ column instead of TIMESTAMP WITHOUT TIME ZONE. Audit
    clarity in a multi-tenant SaaS is worth more than the column-size
    delta, and "every time on the wire is in UTC" is the right invariant.
    """

    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


# Single engine per process. pool_pre_ping guards against stale connections
# after Postgres restarts (frequent in dev with Compose). 3s connect_timeout
# keeps /api/health fast when Postgres is down — health degrades to "db":
# "down" in under 4s rather than hanging on the OS TCP timeout (~75s on
# Linux, multiple minutes on Windows).
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
    connect_args={"connect_timeout": 3},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db():
    """FastAPI dependency that yields a scoped Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
