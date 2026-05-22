"""Agent icon upload + storage.

Single-box local filesystem store. Files live at:
    {RELAY_AGENT_ICON_DIR}/{workspace_id}/{agent_id}.{ext}

Served by nginx at:
    {RELAY_AGENT_ICON_PUBLIC_BASE}/{workspace_id}/{agent_id}.{ext}

This module is the only place that knows the filesystem ↔ URL mapping.
Swap to S3 later by replacing the body of `save_icon` and `delete_icon`
with bucket I/O — call sites and the URL shape don't change.

Validation contract (raises AgentIconError otherwise):
  - content_type ∈ {image/png, image/jpeg, image/gif}
  - file size ≤ RELAY_AGENT_ICON_MAX_BYTES
  - magic-byte check matches content_type (no spoofed types)

We deliberately don't pillow-decode the image — adds a heavy dep + a
CVE surface — but we do check the first ~12 bytes for the standard
signatures. Slack only fetches the URL; it does its own decoding.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from relay_api.core.config import settings


class AgentIconError(Exception):
    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SavedIcon:
    public_url: str
    ext: str


# (content_type, file-extension, magic-byte signatures)
_ALLOWED: tuple[tuple[str, str, tuple[bytes, ...]], ...] = (
    ("image/png", "png", (b"\x89PNG\r\n\x1a\n",)),
    ("image/jpeg", "jpg", (b"\xff\xd8\xff",)),
    ("image/gif", "gif", (b"GIF87a", b"GIF89a")),
)


def _match_content_type(content_type: str, head: bytes) -> tuple[str, str]:
    """Return (normalized content_type, file_ext). Raise on mismatch."""
    ct = (content_type or "").lower().split(";")[0].strip()
    for allowed_ct, ext, signatures in _ALLOWED:
        if ct != allowed_ct:
            continue
        if any(head.startswith(sig) for sig in signatures):
            return ct, ext
        raise AgentIconError(
            "file contents don't match the declared image type",
            code="bad_image",
        )
    raise AgentIconError(
        "icon must be a PNG, JPEG, or GIF",
        code="bad_image_type",
    )


def save_icon(
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    content: bytes,
    content_type: str,
) -> SavedIcon:
    """Persist `content` to disk and return the public URL.

    Overwrites any existing icon for this agent (we name by agent_id, so
    a re-upload just stomps the old file).

    Raises AgentIconError on:
      too_large            — content > RELAY_AGENT_ICON_MAX_BYTES
      bad_image_type       — content_type isn't image/png|jpeg|gif
      bad_image            — magic bytes don't match declared type
      storage_error        — filesystem write failed
    """
    if len(content) > settings.RELAY_AGENT_ICON_MAX_BYTES:
        max_mb = settings.RELAY_AGENT_ICON_MAX_BYTES / 1_048_576
        raise AgentIconError(
            f"icon must be {max_mb:.1f} MB or smaller",
            code="too_large",
        )
    if len(content) < 16:
        raise AgentIconError("file looks empty or truncated", code="bad_image")

    _, ext = _match_content_type(content_type, content[:12])

    workspace_dir = Path(settings.RELAY_AGENT_ICON_DIR) / str(workspace_id)
    try:
        workspace_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise AgentIconError(
            f"couldn't create icon storage dir: {e}",
            code="storage_error",
        ) from e

    # Stomp every extension we know about — if the user previously
    # uploaded a PNG and now uploads a JPEG, the PNG must go.
    for old_ext in ("png", "jpg", "gif"):
        old_path = workspace_dir / f"{agent_id}.{old_ext}"
        if old_path.exists():
            try:
                old_path.unlink()
            except OSError:
                pass  # not fatal; new file will take precedence by URL

    target = workspace_dir / f"{agent_id}.{ext}"
    tmp = target.with_suffix(f".{ext}.tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, target)
    except OSError as e:
        raise AgentIconError(
            f"couldn't write icon to disk: {e}",
            code="storage_error",
        ) from e

    base = settings.RELAY_AGENT_ICON_PUBLIC_BASE.rstrip("/")
    public_url = f"{base}/{workspace_id}/{agent_id}.{ext}"
    return SavedIcon(public_url=public_url, ext=ext)


def delete_icon(
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> None:
    """Remove all stored icon files for this agent. Safe to call when
    nothing exists. Never raises — best-effort cleanup."""
    workspace_dir = Path(settings.RELAY_AGENT_ICON_DIR) / str(workspace_id)
    for ext in ("png", "jpg", "gif"):
        path = workspace_dir / f"{agent_id}.{ext}"
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
