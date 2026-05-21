"""Pytest fixtures shared across the test suite.

Sets a deterministic master key + a Postgres URL for ORM tests. Tests that
need a real DB are decorated with @pytest.mark.dbtest; those skip in CI
environments without Postgres (use `pytest -m "not dbtest"` to skip locally
too if you don't want to spin up docker-compose).
"""
from __future__ import annotations

import base64
import os

# Set BEFORE relay_api imports — these are read at module import.
os.environ.setdefault(
    "RELAY_MASTER_KEY_B64",
    base64.b64encode(b"\x00" * 32).decode("ascii"),
)
# Default to the docker-compose Postgres URL; override in CI via env.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://relay:relay_dev@localhost:5432/relay_dev",
)
