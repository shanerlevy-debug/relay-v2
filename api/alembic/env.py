"""Alembic environment.

Imports the SQLAlchemy `Base` from relay_api.db.session so autogenerate
sees every model registered against it. Models will land in
relay_api/db/models.py in week 1 day 4; for now Base has no tables.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from relay_api.core.config import settings
from relay_api.db.session import Base

# Import models module so all subclasses register on Base.metadata before
# alembic snapshots it. The import is bare (no symbols used) on purpose —
# the side effect is what matters.
try:
    from relay_api.db import models  # noqa: F401
except ImportError:
    # Pre-week-1-day-4 — models module doesn't exist yet. Skip silently;
    # autogenerate will just find an empty schema. Once models.py lands
    # the import succeeds and autogenerate starts producing migrations.
    pass

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pull the DB URL from settings rather than alembic.ini so env-var overrides
# (e.g. tests pointing at a separate DB) take effect.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without an active database connection.

    Emits SQL strings. Useful for generating SQL files to apply elsewhere.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
