"""BYO Anthropic API key — set / get / delete, envelope-encrypted at rest.

One key per workspace. Bridge calls `get_plaintext_key` JIT before each
CMA session create; never caches the plaintext.

API surface never returns the plaintext — only `has_key: bool`. Replacing
a key is an UPSERT (no separate update-vs-create branch from the UI side).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from relay_api.db.models import WorkspaceAnthropicKey
from relay_api.services.envelope import decrypt, encrypt

_MIN_KEY_LEN = 10  # sk-ant-… plus enough characters to be plausibly real


class AnthropicKeyError(Exception):
    def __init__(self, message: str, *, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(UTC)


def has_key(db: Session, *, workspace_id: uuid.UUID) -> bool:
    return (
        db.execute(
            select(WorkspaceAnthropicKey.workspace_id)
            .where(WorkspaceAnthropicKey.workspace_id == workspace_id)
        ).first()
        is not None
    )


def set_key(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    raw_key: str,
    created_by_user_id: uuid.UUID,
) -> WorkspaceAnthropicKey:
    """UPSERT — replace any existing key for this workspace.

    Raises AnthropicKeyError on malformed input; encryption errors bubble
    up as EnvelopeError (500 at the route).
    """
    raw_key = raw_key.strip()
    if len(raw_key) < _MIN_KEY_LEN:
        raise AnthropicKeyError("key looks too short", code="invalid_key")
    if not raw_key.startswith("sk-ant-"):
        # Soft warning — Anthropic-issued keys all start with this prefix.
        # If they ever change the format we'll have to relax this; for now
        # rejecting saves users from a typo that'd only fail at session-create.
        raise AnthropicKeyError(
            "key must start with 'sk-ant-' (Anthropic-issued)",
            code="invalid_key_format",
        )

    aad = workspace_id.bytes
    nonce, ct = encrypt(raw_key, aad=aad)

    existing = db.execute(
        select(WorkspaceAnthropicKey).where(
            WorkspaceAnthropicKey.workspace_id == workspace_id
        )
    ).scalar_one_or_none()

    if existing is None:
        row = WorkspaceAnthropicKey(
            workspace_id=workspace_id,
            key_nonce=nonce,
            key_ct=ct,
            created_by_user_id=created_by_user_id,
        )
        db.add(row)
    else:
        existing.key_nonce = nonce
        existing.key_ct = ct
        existing.updated_at = _now()
        existing.created_by_user_id = created_by_user_id  # track most recent setter
        row = existing

    db.flush()
    return row


def delete_key(db: Session, *, workspace_id: uuid.UUID) -> bool:
    """Remove the key. Returns True if a row was removed, False if absent."""
    existing = db.execute(
        select(WorkspaceAnthropicKey).where(
            WorkspaceAnthropicKey.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if existing is None:
        return False
    db.delete(existing)
    db.flush()
    return True


def get_plaintext_key(
    db: Session,
    *,
    workspace_id: uuid.UUID,
) -> str | None:
    """Bridge's read path. Returns plaintext or None if no key configured.

    Never log the return value — it's a credential.
    """
    row = db.execute(
        select(WorkspaceAnthropicKey).where(
            WorkspaceAnthropicKey.workspace_id == workspace_id
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return decrypt(
        nonce=bytes(row.key_nonce),
        ciphertext=bytes(row.key_ct),
        aad=row.workspace_id.bytes,
    )
