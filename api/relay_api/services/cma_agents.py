"""CMA discovery — list agents + environments the user's BYOK has access to.

Powers the browse-and-pick Add Agent screen on /agents. Each call:
  1. Pulls the plaintext BYOK from envelope storage (JIT decrypt).
  2. Instantiates the Anthropic SDK client.
  3. Calls the relevant `client.beta.{agents,environments}.list()` endpoint.
  4. Returns a plain-list result (we paginate exhaustively — list-mode UIs
     should not stutter on pagination, and CMA lists are tiny in practice).

Errors map to `CmaDiscoveryError` codes the route layer turns into clean
4xx responses:
  byok_missing      — no Anthropic key set for this workspace
  byok_invalid      — Anthropic returned 401 (the saved key was rejected)
  rate_limited      — 429 from upstream
  upstream_error    — anything else (5xx, timeout, network)

Same import shape as Powerloom's wrappers — see
`D:\\Relay\\RELAY-POWERLOOM-AGENT-SELECTOR-HANDOFF.md` for the multi-workspace
adaptation Powerloom needs to layer on top of this.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from anthropic import (
    APIConnectionError,
    APIError,
    APIStatusError,
    Anthropic,
    AuthenticationError,
    RateLimitError,
)
from sqlalchemy.orm import Session

from relay_api.core.logging import get_logger
from relay_api.services.anthropic_key import get_plaintext_key

log = get_logger(__name__)


class CmaDiscoveryError(Exception):
    """Expected failures in CMA list calls. `code` is what the UI branches on."""

    def __init__(self, message: str, *, code: str = "upstream_error"):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CmaAgentSummary:
    """The fields the picker actually shows. Full SDK object has more —
    add fields here only when the UI needs them, otherwise we're shipping
    bytes for no reason."""

    id: str
    model: str | None
    system: str | None          # the system prompt, full
    archived_at: str | None      # ISO-8601 string or None


@dataclass(frozen=True)
class CmaEnvironmentSummary:
    id: str
    name: str | None
    networking_type: str | None  # "limited" | "unrestricted" | None


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------


def _client(db: Session, *, workspace_id: uuid.UUID) -> Anthropic:
    """Resolve BYOK + instantiate the Anthropic SDK client. Raises
    CmaDiscoveryError("byok_missing") if the workspace hasn't set a key.
    """
    key = get_plaintext_key(db, workspace_id=workspace_id)
    if not key:
        raise CmaDiscoveryError(
            "Add an Anthropic API key in Settings → BYOK first.",
            code="byok_missing",
        )
    return Anthropic(api_key=key)


def _map_sdk_error(e: Exception) -> CmaDiscoveryError:
    """Turn an SDK exception into a typed CmaDiscoveryError."""
    if isinstance(e, AuthenticationError):
        return CmaDiscoveryError(
            "Anthropic rejected the saved API key. Check Settings → BYOK.",
            code="byok_invalid",
        )
    if isinstance(e, RateLimitError):
        return CmaDiscoveryError(
            "Anthropic is rate-limiting requests. Try again in a moment.",
            code="rate_limited",
        )
    if isinstance(e, APIStatusError):
        # 4xx/5xx that aren't auth/rate-limit
        return CmaDiscoveryError(
            f"Anthropic returned HTTP {e.status_code}.",
            code="upstream_error",
        )
    if isinstance(e, (APIConnectionError, APIError)):
        return CmaDiscoveryError(
            "Couldn't reach Anthropic. Try again in a moment.",
            code="upstream_error",
        )
    # Anything else — surface generically but log the full type for ops.
    log.warning("cma_discovery.unexpected_error", error_type=type(e).__name__)
    return CmaDiscoveryError(
        "Unexpected error talking to Anthropic.",
        code="upstream_error",
    )


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def list_cma_agents(
    db: Session,
    *,
    workspace_id: uuid.UUID,
) -> list[CmaAgentSummary]:
    """Enumerate every non-archived agent the BYOK can see.

    CMA lists are tiny (most users have <20 agents) so we don't bother
    streaming — pull all pages, return a flat list.
    """
    client = _client(db, workspace_id=workspace_id)
    out: list[CmaAgentSummary] = []
    try:
        for page in client.beta.agents.list().iter_pages():
            for agent in page.data:
                archived = _stringify_dt(getattr(agent, "archived_at", None))
                if archived is not None:
                    continue  # picker shows active agents only
                out.append(CmaAgentSummary(
                    id=str(getattr(agent, "id", "") or ""),
                    model=_stringify(getattr(agent, "model", None)),
                    system=_stringify(getattr(agent, "system", None)),
                    archived_at=archived,
                ))
    except Exception as e:
        raise _map_sdk_error(e) from e
    return out


def list_cma_environments(
    db: Session,
    *,
    workspace_id: uuid.UUID,
) -> list[CmaEnvironmentSummary]:
    """Enumerate every environment the BYOK can see."""
    client = _client(db, workspace_id=workspace_id)
    out: list[CmaEnvironmentSummary] = []
    try:
        for page in client.beta.environments.list().iter_pages():
            for env in page.data:
                cfg = getattr(env, "config", None)
                networking_type = _extract_networking_type(cfg)
                out.append(CmaEnvironmentSummary(
                    id=str(getattr(env, "id", "") or ""),
                    name=_stringify(getattr(env, "name", None)),
                    networking_type=networking_type,
                ))
    except Exception as e:
        raise _map_sdk_error(e) from e
    return out


# ---------------------------------------------------------------------------
# Validation — called by /api/agents POST before insert
# ---------------------------------------------------------------------------


def validate_agent_and_environment(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    agent_id: str,
    environment_id: str,
) -> None:
    """Confirm both IDs exist + are usable against the BYOK.

    Raises CmaDiscoveryError on:
      byok_missing      — same as above
      byok_invalid      — same
      agent_not_found   — agent_id 404s
      env_not_found     — env_id 404s
      upstream_error    — anything else
    """
    client = _client(db, workspace_id=workspace_id)
    try:
        agent = client.beta.agents.retrieve(agent_id)
        if _stringify_dt(getattr(agent, "archived_at", None)) is not None:
            raise CmaDiscoveryError(
                "That agent has been archived in Anthropic.",
                code="agent_archived",
            )
    except APIStatusError as e:
        if e.status_code == 404:
            raise CmaDiscoveryError(
                "Agent not found in your Anthropic workspace.",
                code="agent_not_found",
            ) from e
        raise _map_sdk_error(e) from e
    except Exception as e:
        raise _map_sdk_error(e) from e

    try:
        client.beta.environments.retrieve(environment_id)
    except APIStatusError as e:
        if e.status_code == 404:
            raise CmaDiscoveryError(
                "Environment not found in your Anthropic workspace.",
                code="env_not_found",
            ) from e
        raise _map_sdk_error(e) from e
    except Exception as e:
        raise _map_sdk_error(e) from e


# ---------------------------------------------------------------------------
# Tiny helpers — keep the SDK-shape coupling in one place
# ---------------------------------------------------------------------------


def _stringify(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)


def _stringify_dt(v: Any) -> str | None:
    """ISO-format a datetime/string or return None. SDK sometimes returns
    aware-datetime, sometimes string — accept both."""
    if v is None:
        return None
    isoformat = getattr(v, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            pass
    return _stringify(v)


def _extract_networking_type(cfg: Any) -> str | None:
    """Pull `config.networking.type` out of an env config object. The SDK
    returns it as a typed object or dict depending on shape; we coerce."""
    if cfg is None:
        return None
    networking = getattr(cfg, "networking", None)
    if networking is None and isinstance(cfg, dict):
        networking = cfg.get("networking")
    if networking is None:
        return None
    t = getattr(networking, "type", None)
    if t is None and isinstance(networking, dict):
        t = networking.get("type")
    return _stringify(t)
