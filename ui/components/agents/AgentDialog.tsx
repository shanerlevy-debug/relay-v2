"use client";

import { FormEvent, useEffect, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import {
  AgentCreateRequest,
  AgentOut,
  AgentUpdateRequest,
  ApiError,
  createAgent,
  updateAgent,
} from "@/lib/api";

const SLUG_RE = /^[a-z][a-z0-9-]*$/;

/**
 * New-agent + edit-agent dialog. Same form shape; the difference is
 * whether we POST or PATCH and which fields are prefilled. Validated
 * client-side first; API errors surface inline.
 */
interface AgentDialogProps {
  open: boolean;
  onClose: () => void;
  onSaved: (agent: AgentOut) => void;
  /** When provided, the dialog is in edit mode. */
  editing?: AgentOut | null;
}

export function AgentDialog({ open, onClose, onSaved, editing }: AgentDialogProps) {
  const [slug, setSlug] = useState("");
  const [anthropicAgentId, setAnthropicAgentId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [description, setDescription] = useState("");
  const [isDefault, setIsDefault] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorField, setErrorField] = useState<keyof typeof FIELD_ERRORS | null>(null);

  // Initialize / reset form when opening
  useEffect(() => {
    if (!open) return;
    if (editing) {
      setSlug(editing.slug);
      setAnthropicAgentId(editing.anthropic_agent_id);
      setEnvironmentId(editing.environment_id);
      setDescription(editing.description ?? "");
      setIsDefault(editing.is_default);
    } else {
      setSlug("");
      setAnthropicAgentId("");
      setEnvironmentId("");
      setDescription("");
      setIsDefault(false);
    }
    setError(null);
    setErrorField(null);
  }, [open, editing]);

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
          setErrorField(mapped.field as keyof typeof FIELD_ERRORS);
        } else {
          setError(err.message);
        }
      } else {
        setError("Something went wrong. Try again.");
      }
      setSubmitting(false);
    }
  }

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
      maxWidth={500}
    >
      <form onSubmit={onSubmit}>
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
            autoFocus={!editing}
            pattern="[a-z][a-z0-9\-]*"
          />
        </Field>

        <Field
          label="Anthropic agent ID"
          hint="from the Anthropic Console — starts with agent_"
          error={errorField === "anthropic_agent_id" ? error : null}
        >
          <input
            type="text"
            value={anthropicAgentId}
            onChange={(e) => setAnthropicAgentId(e.target.value)}
            className="rl-input"
            placeholder="agent_011..."
            required
            disabled={submitting}
            maxLength={64}
          />
        </Field>

        <Field
          label="Environment ID"
          hint="from the Anthropic Console — starts with env_"
          error={errorField === "environment_id" ? error : null}
        >
          <input
            type="text"
            value={environmentId}
            onChange={(e) => setEnvironmentId(e.target.value)}
            className="rl-input"
            placeholder="env_018..."
            required
            disabled={submitting}
            maxLength={64}
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

const FIELD_ERRORS = {
  slug: { field: "slug", message: "slug must start with a letter and use only lowercase/digits/hyphens" },
  invalid_slug: { field: "slug", message: "slug must start with a letter and use only lowercase/digits/hyphens" },
  slug_in_use: { field: "slug", message: "an active agent already uses this slug" },
  anthropic_agent_id: { field: "anthropic_agent_id", message: "anthropic_agent_id required" },
  environment_id: { field: "environment_id", message: "environment_id required" },
  archived: { field: "general", message: "this agent is archived — restore it first" },
} as const;

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
