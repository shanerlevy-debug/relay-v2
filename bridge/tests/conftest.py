"""Pytest config — set the same master key + DB URL the API tests use."""
from __future__ import annotations

import base64
import os

os.environ.setdefault(
    "RELAY_MASTER_KEY_B64",
    base64.b64encode(b"\x00" * 32).decode("ascii"),
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://relay:relay_dev@localhost:5432/relay_dev",
)
# Bridge-specific: tests don't need a real Slack App Token; main.create_app
# isn't called in unit tests. Set a fake so any code that introspects
# settings doesn't trip.
os.environ.setdefault("RELAY_SLACK_APP_TOKEN", "xapp-fake-for-tests")
