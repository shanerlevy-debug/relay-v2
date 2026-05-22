"use client";

import { ChevronDown, ExternalLink, Loader2 } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import {
  AgentCreateRequest,
  AgentOut,
  AgentUpdateRequest,
  ApiError,
  CmaAgentSummary,
  CmaEnvironmentSummary,
  createAgent,
  listCmaAgents,
  listCmaEnvironments,
  updateAgent,
} from "@/lib/api";

const SLUG_RE = /^[a-z][a-z0-9-]*$/;

/**
 * Add / edit agent dialog with two creation modes:
 *
 * - **Browse**  (default for new agents): fetches the user's CMA agents +
 *   environments via the BYOK and lets them pick. Single-workspace —
 *   Powerloom adds a workspace selector on top, see
 *   D:\Relay\RELAY-POWERLOOM-AGENT-SELECTOR-HANDOFF.md.
 * - **Paste ID** (fallback): the original form. Kept for power users who
 *   want full control or whose Anthropic key isn't set yet.
 *
 * Edit mode reuses the Paste shape only — the underlying agent already
 * exists, so the pickers add no value.
 */
interface AgentDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: (agent: AgentOut) => void;
  /** When provided, the dialog is in edit mode. */
  editing?: AgentOut | null;
}

type Mode = "browse" | "paste";

export function AgentDialog({ open, onClose, onSaved, editing }: AgentDialogProps) {
  const isEdit = editing !== null && editing !== undefined;
  const [mode, setMode] = useState<Mode>("browse");

  // Shared form state
  const [slug, setSlug] = useState("");
  const [anthropicAgentId, setAnthropicAgentId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [description, setDescription] = useState("");
  const [isDefault, setIsDefault] = useState(false);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorField, setErrorField] = useState<string | null>(null);

  // Browse-mode state
  const [browseLoading, setBrowseLoading] = useState(false);
  const [browseError, setBrowseError] = useState<{ code: string; message: string } | null>(null);
  const [cmaAgents, setCmaAgents] = useState<CmaAgentSummary[]>([]);
  const [cmaEnvironments, setCmaEnvironments] = useState<CmaEnvironmentSummary[]>([]);

  // Reset on open
  useEffect(() => {
    if (!open) return;
    if (editing) {
      setMode("paste");
      setSlug(editing.slug);
      setAnthropicAgentId(editing.anthropic_agent_id);
      setEnvironmentId(editing.environment_id);
      setDescription(editing.description ?? "");
      setIsDefault(editing.is_default);
    } else {
      setMode("browse");
      setSlug("");
      setAnthropicAgentId("");
      setEnvironmentId("");
      setDescription("");
      setIsDefault(false);
    }
    setError(null);
    setErrorField(null);
    setBrowseError(null);
  }, [open, editing]);

  // Fetch CMA lists when we land on browse mode (or change to it)
  useEffect(() => {
    if (!open || isEdit || mode !== "browse") return;
    let cancelled = false;
    setBrowseLoading(true);
    setBrowseError(null);
    Promise.all([listCmaAgents(), listCmaEnvironments()])
      .then(([a, e]) => {
        if (cancelled) return;
        setCmaAgents(a.agents);
        setCmaEnvironments(e.environments);
        // Auto-select the first environment if the user has exactly one — that's
        // the common case for a workspace using Relay's default-env-per-tenant pattern.
        if (e.environments.length === 1) {
          setEnvironmentId(e.environments[0].id);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError) {
          setBrowseError({ code: err.code, message: err.message });
        } else {
          setBrowseError({ code: "client_error", message: "Couldn't load your CMA agents." });
        }
      })
      .finally(() => {
        if (!cancelled) setBrowseLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, isEdit, mode]);

  function validateSlug(value: string): string | null {
    if (!value) return "slug is required";
    if (!SLUG_RE.test(value)) return "lowercase letters/digits/hyphens, starts with a letter";
    if (value.length > 64) return "max 64 characters";
    return null;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setErrorField(null);

    const slugError = validateSlug(slug.trim().toLowerCase());
    if (slugError) {
      setError(slugError);
      setErrorField("slug");
      return;
    }
    if (!anthropicAgentId.trim()) {
      setError("pick an agent");
      setErrorField("anthropic_agent_id");
      return;
    }
    if (!environmentId.trim()) {
      setError("pick an environment");
      setErrorField("environment_id");
      return;
    }

    setSubmitting(true);
    try {
      if (editing) {
        const req: AgentUpdateRequest = {
          slug: slug.trim().toLowerCase(),
          anthropic_agent_id: anthropicAgentId.trim(),
          environment_id: environmentId.trim(),
          description: description.trim() || null,
          is_default: isDefault,
        };
        const updated = await updateAgent(editing.id, req);
        onSaved(updated);
      } else {
        const req: AgentCreateRequest = {
          slug: slug.trim().toLowerCase(),
          anthropic_agent_id: anthropicAgentId.trim(),
          environment_id: environmentId.trim(),
          description: description.trim() || null,
          is_default: isDefault,
        };
        const created = await createAgent(req);
        onSaved(created);
      }
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        const mapped = FIELD_ERRORS[err.code as keyof typeof FIELD_ERRORS];
        if (mapped) {
          setError(mapped.message);
          setErrorField(mapped.field);
        } else {
          setError(err.message);
        }
      } else {
        setError("Something went wrong. Try again.");
      }
      setSubmitting(false);
    }
  }

  const selectedAgent = cmaAgents.find((a) => a.id === anthropicAgentId) ?? null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={editing ? `Edit ${editing.slug}` : "New agent"}
      description={
        editing
          ? "Rename, switch the underlying Anthropic agent, or change the default flag."
          : "Address this agent in Slack as @relay <slug> ... or /relay <slug> ..."
      }
      maxWidth={560}
    >
      {!isEdit && (
        <ModeTabs mode={mode} onChange={setMode} disabled={submitting} />
      )}

      <form onSubmit={onSubmit}>
        {!isEdit && mode === "browse" ? (
          <BrowsePane
            loading={browseLoading}
            error={browseError}
            agents={cmaAgents}
            environments={cmaEnvironments}
            anthropicAgentId={anthropicAgentId}
            environmentId={environmentId}
            onPickAgent={setAnthropicAgentId}
            onPickEnvironment={setEnvironmentId}
            selectedAgent={selectedAgent}
            errorField={errorField}
            disabled={submitting}
          />
        ) : (
          <PastePane
            anthropicAgentId={anthropicAgentId}
            environmentId={environmentId}
            onChangeAgentId={setAnthropicAgentId}
            onChangeEnvironmentId={setEnvironmentId}
            errorField={errorField}
            error={error}
            disabled={submitting}
            isEdit={isEdit}
          />
        )}

        <Field
          label="Slug"
          hint="lowercase, letters/digits/hyphens, starts with a letter"
          error={errorField === "slug" ? error : null}
        >
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="rl-input"
            placeholder="vanguard"
            required
            disabled={submitting}
            maxLength={64}
            pattern="[a-z][a-z0-9\-]*"
          />
        </Field>

        <Field label="Description" hint="optional · max 1024 characters" error={null}>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="rl-input"
            placeholder="Deep research with web search."
            rows={2}
            maxLength={1024}
            disabled={submitting}
            style={{ fontFamily: "inherit", resize: "vertical", minHeight: 48 }}
          />
        </Field>

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "10px 12px",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            fontSize: 13,
            cursor: "pointer",
            marginTop: 8,
            marginBottom: 16,
          }}
        >
          <input
            type="checkbox"
            checked={isDefault}
            onChange={(e) => setIsDefault(e.target.checked)}
            disabled={submitting}
          />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 500 }}>Make this the default agent</div>
            <div style={{ fontSize: 12, color: "var(--color-fg3)", marginTop: 2 }}>
              Handles untagged @relay messages and DMs.
            </div>
          </div>
        </label>

        {error && !errorField && (
          <div
            style={{
              padding: "10px 12px",
              background: "var(--color-danger-tint)",
              border: "1px solid var(--color-danger-border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-danger)",
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            type="button"
            onClick={onClose}
            className="rl-btn rl-btn-ghost"
            disabled={submitting}
          >
            Cancel
          </button>
          <button type="submit" className="rl-btn rl-btn-primary" disabled={submitting}>
            {submitting ? "Saving…" : editing ? "Save changes" : "Add agent"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Mode tabs
// ---------------------------------------------------------------------------

function ModeTabs({
  mode,
  onChange,
  disabled,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
  disabled: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        padding: 4,
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-sm)",
        marginBottom: 16,
      }}
    >
      <TabButton active={mode === "browse"} onClick={() => onChange("browse")} disabled={disabled}>
        Browse my agents
      </TabButton>
      <TabButton active={mode === "paste"} onClick={() => onChange("paste")} disabled={disabled}>
        Paste agent ID
      </TabButton>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  disabled,
  children,
}: {
  active: boolean;
  onClick: () => void;
  disabled: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        flex: 1,
        padding: "8px 12px",
        background: active ? "var(--color-surface-2)" : "transparent",
        border: 0,
        borderRadius: "calc(var(--radius-sm) - 2px)",
        fontSize: 13,
        fontWeight: active ? 500 : 400,
        color: active ? "var(--color-fg1)" : "var(--color-fg3)",
        cursor: disabled ? "not-allowed" : "pointer",
        fontFamily: "inherit",
        boxShadow: active ? "0 1px 2px rgb(0 0 0 / 0.04)" : "none",
        transition: "background 120ms var(--ease-std)",
      }}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Browse pane (pickers)
// ---------------------------------------------------------------------------

function BrowsePane({
  loading,
  error,
  agents,
  environments,
  anthropicAgentId,
  environmentId,
  onPickAgent,
  onPickEnvironment,
  selectedAgent,
  errorField,
  disabled,
}: {
  loading: boolean;
  error: { code: string; message: string } | null;
  agents: CmaAgentSummary[];
  environments: CmaEnvironmentSummary[];
  anthropicAgentId: string;
  environmentId: string;
  onPickAgent: (id: string) => void;
  onPickEnvironment: (id: string) => void;
  selectedAgent: CmaAgentSummary | null;
  errorField: string | null;
  disabled: boolean;
}) {
  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 10,
          padding: "32px 16px",
          color: "var(--color-fg3)",
          fontSize: 13,
        }}
      >
        <Loader2 size={16} className="rl-spin" />
        Loading your CMA agents…
      </div>
    );
  }

  if (error) {
    return <BrowseError error={error} />;
  }

  if (agents.length === 0) {
    return (
      <div
        style={{
          padding: "16px 14px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          fontSize: 13,
          color: "var(--color-fg2)",
          marginBottom: 14,
          lineHeight: 1.5,
        }}
      >
        Your Anthropic key works but doesn&apos;t have any agents yet. Create one in{" "}
        <a
          href="https://console.anthropic.com/"
          target="_blank"
          rel="noreferrer"
          className="link"
          style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
        >
          console.anthropic.com
          <ExternalLink size={11} />
        </a>
        , then come back here.
      </div>
    );
  }

  return (
    <>
      <Field
        label="Anthropic agent"
        hint={`${agents.length} active`}
        error={errorField === "anthropic_agent_id" ? "pick one" : null}
      >
        <div style={{ position: "relative" }}>
          <select
            value={anthropicAgentId}
            onChange={(e) => onPickAgent(e.target.value)}
            disabled={disabled}
            className="rl-input"
            style={{ appearance: "none", paddingRight: 32 }}
            required
          >
            <option value="">Pick an agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {agentLabel(a)}
              </option>
            ))}
          </select>
          <ChevronDown
            size={14}
            style={{
              position: "absolute",
              right: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--color-fg3)",
              pointerEvents: "none",
            }}
          />
        </div>
      </Field>

      {selectedAgent && selectedAgent.system && (
        <div
          style={{
            padding: "10px 12px",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border-subtle)",
            borderRadius: "var(--radius-sm)",
            fontSize: 12,
            lineHeight: 1.5,
            color: "var(--color-fg2)",
            marginTop: -6,
            marginBottom: 14,
            maxHeight: 110,
            overflow: "auto",
            whiteSpace: "pre-wrap",
            fontFamily: "var(--font-mono)",
          }}
        >
          {selectedAgent.system}
        </div>
      )}

      <Field
        label="Environment"
        hint={
          environments.length === 0
            ? "no environments"
            : environments.length === 1
              ? "auto-selected"
              : `${environments.length} available`
        }
        error={errorField === "environment_id" ? "pick one" : null}
      >
        {environments.length === 0 ? (
          <div
            style={{
              padding: "10px 12px",
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              fontSize: 12,
              color: "var(--color-fg3)",
              lineHeight: 1.5,
            }}
          >
            Your Anthropic key has no environments. Create one in{" "}
            <a
              href="https://console.anthropic.com/"
              target="_blank"
              rel="noreferrer"
              className="link"
            >
              console.anthropic.com
            </a>{" "}
            and try again.
          </div>
        ) : (
          <div style={{ position: "relative" }}>
            <select
              value={environmentId}
              onChange={(e) => onPickEnvironment(e.target.value)}
              disabled={disabled}
              className="rl-input"
              style={{ appearance: "none", paddingRight: 32 }}
              required
            >
              <option value="">Pick an environment…</option>
              {environments.map((env) => (
                <option key={env.id} value={env.id}>
                  {environmentLabel(env)}
                </option>
              ))}
            </select>
            <ChevronDown
              size={14}
              style={{
                position: "absolute",
                right: 10,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--color-fg3)",
                pointerEvents: "none",
              }}
            />
          </div>
        )}
      </Field>
    </>
  );
}

function BrowseError({ error }: { error: { code: string; message: string } }) {
  // BYOK problems get a high-signal banner + link to Settings. Everything
  // else is generic — but always show the upstream message so it's not a
  // total black box.
  if (error.code === "byok_missing") {
    return (
      <div
        style={{
          padding: "14px 14px",
          background: "var(--color-relay-tint, rgba(255, 138, 95, 0.08))",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          fontSize: 13,
          color: "var(--color-fg2)",
          marginBottom: 14,
          lineHeight: 1.5,
        }}
      >
        <strong style={{ display: "block", marginBottom: 4, color: "var(--color-fg1)" }}>
          Add an Anthropic key first
        </strong>
        We need a BYOK key to list your CMA agents.{" "}
        <Link href="/settings" className="link">
          Open Settings → BYOK
        </Link>
        , paste your key, then come back to add an agent.
      </div>
    );
  }
  if (error.code === "byok_invalid") {
    return (
      <div
        style={{
          padding: "14px 14px",
          background: "var(--color-danger-tint)",
          border: "1px solid var(--color-danger-border)",
          borderRadius: "var(--radius-sm)",
          fontSize: 13,
          color: "var(--color-danger)",
          marginBottom: 14,
          lineHeight: 1.5,
        }}
      >
        <strong style={{ display: "block", marginBottom: 4 }}>
          Anthropic rejected your key
        </strong>
        It may have been rotated or revoked.{" "}
        <Link href="/settings" className="link">
          Update it in Settings → BYOK
        </Link>{" "}
        and try again.
      </div>
    );
  }
  return (
    <div
      style={{
        padding: "14px 14px",
        background: "var(--color-danger-tint)",
        border: "1px solid var(--color-danger-border)",
        borderRadius: "var(--radius-sm)",
        fontSize: 13,
        color: "var(--color-danger)",
        marginBottom: 14,
      }}
    >
      {error.message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Paste pane (legacy form)
// ---------------------------------------------------------------------------

function PastePane({
  anthropicAgentId,
  environmentId,
  onChangeAgentId,
  onChangeEnvironmentId,
  errorField,
  error,
  disabled,
  isEdit,
}: {
  anthropicAgentId: string;
  environmentId: string;
  onChangeAgentId: (v: string) => void;
  onChangeEnvironmentId: (v: string) => void;
  errorField: string | null;
  error: string | null;
  disabled: boolean;
  isEdit: boolean;
}) {
  return (
    <>
      <Field
        label="Anthropic agent ID"
        hint="from console.anthropic.com — starts with agent_"
        error={errorField === "anthropic_agent_id" ? error : null}
      >
        <input
          type="text"
          value={anthropicAgentId}
          onChange={(e) => onChangeAgentId(e.target.value)}
          className="rl-input"
          placeholder="agent_011..."
          required
          disabled={disabled}
          maxLength={64}
          autoFocus={!isEdit}
        />
      </Field>

      <Field
        label="Environment ID"
        hint="from console.anthropic.com — starts with env_"
        error={errorField === "environment_id" ? error : null}
      >
        <input
          type="text"
          value={environmentId}
          onChange={(e) => onChangeEnvironmentId(e.target.value)}
          className="rl-input"
          placeholder="env_018..."
          required
          disabled={disabled}
          maxLength={64}
        />
      </Field>
    </>
  );
}

// ---------------------------------------------------------------------------
// Picker label helpers
// ---------------------------------------------------------------------------

function agentLabel(a: CmaAgentSummary): string {
  const model = a.model ?? "(unknown model)";
  const systemPreview = preview(a.system, 60);
  if (systemPreview) {
    return `${a.id.slice(0, 14)}…  ·  ${model}  —  ${systemPreview}`;
  }
  return `${a.id}  ·  ${model}`;
}

function environmentLabel(e: CmaEnvironmentSummary): string {
  const name = e.name ?? e.id;
  const net = e.networking_type ? ` (${e.networking_type} network)` : "";
  return `${name}${net}`;
}

function preview(s: string | null, n: number): string | null {
  if (!s) return null;
  const flat = s.replace(/\s+/g, " ").trim();
  if (flat.length <= n) return flat;
  return flat.slice(0, n - 1).trimEnd() + "…";
}

// ---------------------------------------------------------------------------
// Field shell
// ---------------------------------------------------------------------------

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label
        style={{
          display: "block",
          fontSize: 12,
          fontWeight: 500,
          color: "var(--color-fg2)",
          marginBottom: 6,
        }}
      >
        {label}
        {hint && (
          <span style={{ fontWeight: 400, color: "var(--color-fg3)", marginLeft: 6, fontSize: 11 }}>
            {hint}
          </span>
        )}
      </label>
      {children}
      {error && (
        <div style={{ fontSize: 12, color: "var(--color-danger)", marginTop: 4 }}>{error}</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Server-error → form-field mapping
// ---------------------------------------------------------------------------

const FIELD_ERRORS: Record<string, { field: string; message: string }> = {
  slug: { field: "slug", message: "slug must start with a letter and use only lowercase/digits/hyphens" },
  invalid_slug: { field: "slug", message: "slug must start with a letter and use only lowercase/digits/hyphens" },
  slug_in_use: { field: "slug", message: "an active agent already uses this slug" },
  anthropic_agent_id: { field: "anthropic_agent_id", message: "anthropic_agent_id required" },
  environment_id: { field: "environment_id", message: "environment_id required" },
  archived: { field: "general", message: "this agent is archived — restore it first" },
};
