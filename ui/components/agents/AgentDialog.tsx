"use client";

import { ChevronDown, ExternalLink, Image as ImageIcon, Loader2, Smile, X } from "lucide-react";
import Link from "next/link";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import {
  AgentCreateRequest,
  AgentOut,
  AgentUpdateRequest,
  ApiError,
  CmaAgentSummary,
  CmaEnvironmentSummary,
  createAgent,
  deleteAgentIcon,
  listCmaAgents,
  listCmaEnvironments,
  updateAgent,
  uploadAgentIcon,
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

  // Persona state — Slack identity overrides.
  //
  // iconValue holds the *persisted* slack_icon_url (either `:emoji:` or `https://...`)
  // OR is "" if cleared. pendingFile holds a freshly-picked File the user wants
  // uploaded on save. iconKind switches the UI between emoji / file modes.
  const [slackDisplayName, setSlackDisplayName] = useState("");
  const [iconKind, setIconKind] = useState<"none" | "emoji" | "file">("none");
  const [iconEmoji, setIconEmoji] = useState("");
  const [iconUrl, setIconUrl] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
      setSlackDisplayName(editing.slack_display_name ?? "");
      const existing = editing.slack_icon_url ?? "";
      if (existing.startsWith(":") && existing.endsWith(":")) {
        setIconKind("emoji");
        setIconEmoji(existing);
        setIconUrl(null);
      } else if (existing.startsWith("https://")) {
        setIconKind("file");
        setIconEmoji("");
        setIconUrl(existing);
      } else {
        setIconKind("none");
        setIconEmoji("");
        setIconUrl(null);
      }
    } else {
      setMode("browse");
      setSlug("");
      setAnthropicAgentId("");
      setEnvironmentId("");
      setDescription("");
      setIsDefault(false);
      setSlackDisplayName("");
      setIconKind("none");
      setIconEmoji("");
      setIconUrl(null);
    }
    setPendingFile(null);
    setPendingPreview(null);
    setError(null);
    setErrorField(null);
    setBrowseError(null);
  }, [open, editing]);

  function onPickFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (!file) return;
    setPendingFile(file);
    setIconKind("file");
    setIconEmoji("");
    // Local object URL for the preview pill. Revoked when the dialog
    // re-opens (effectively when component remounts) or when we save.
    if (pendingPreview) URL.revokeObjectURL(pendingPreview);
    setPendingPreview(URL.createObjectURL(file));
  }

  function onClearIcon() {
    setIconKind("none");
    setIconEmoji("");
    setIconUrl(null);
    if (pendingPreview) URL.revokeObjectURL(pendingPreview);
    setPendingPreview(null);
    setPendingFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

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
    if (!value) return "display name is required";
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

    // Compute the slack_icon_url JSON value based on iconKind:
    //   none   → null (clear it)
    //   emoji  → the emoji string (validated server-side)
    //   file   → leave the column alone in the PATCH/POST body; the actual
    //            upload happens as a second API call after the row exists
    let iconUrlForBody: string | null | undefined;
    if (iconKind === "none") {
      iconUrlForBody = null; // explicit clear
    } else if (iconKind === "emoji") {
      const e = iconEmoji.trim();
      if (e && !/^:[a-z0-9_+\-]+:$/.test(e)) {
        setError("emoji must look like :books: — colons, lowercase, underscores, hyphens");
        setErrorField("slack_icon_url");
        return;
      }
      iconUrlForBody = e || null;
    } else {
      // file mode — don't touch the URL field in the JSON body; upload step handles it.
      iconUrlForBody = undefined;
    }

    setSubmitting(true);
    try {
      const trimmedName = slackDisplayName.trim();
      const baseBody = {
        slug: slug.trim().toLowerCase(),
        anthropic_agent_id: anthropicAgentId.trim(),
        environment_id: environmentId.trim(),
        description: description.trim() || null,
        is_default: isDefault,
        slack_display_name: trimmedName || null,
        ...(iconUrlForBody !== undefined && { slack_icon_url: iconUrlForBody }),
      };

      let saved: AgentOut;
      if (editing) {
        saved = await updateAgent(editing.id, baseBody as AgentUpdateRequest);
      } else {
        saved = await createAgent(baseBody as AgentCreateRequest);
      }

      // Second pass — wrapped separately so an upload failure doesn't
      // make it look like the whole save failed (the agent row is already
      // committed at this point). Surface the upload error inline; the
      // parent gets onSaved with the pre-upload row so the list refreshes.
      if (pendingFile) {
        try {
          saved = await uploadAgentIcon(saved.id, pendingFile);
        } catch (uploadErr) {
          onSaved(saved);
          if (uploadErr instanceof ApiError) {
            const mapped = FIELD_ERRORS[uploadErr.code as keyof typeof FIELD_ERRORS];
            setError(mapped?.message ?? uploadErr.message);
            setErrorField(mapped?.field ?? "slack_icon_url");
          } else {
            setError("Couldn't upload the icon. Try a smaller PNG/JPEG/GIF.");
            setErrorField("slack_icon_url");
          }
          setSubmitting(false);
          return;
        }
      } else if (
        iconKind === "none" &&
        editing?.slack_icon_url?.startsWith("https://")
      ) {
        saved = await deleteAgentIcon(saved.id);
      }

      onSaved(saved);
      if (pendingPreview) URL.revokeObjectURL(pendingPreview);
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
          : "Address this agent in Slack as @relay <name> ... or /relay <name> ..."
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
          label="Name"
          hint="used to address the agent: @relay <name>. lowercase, letters/digits/hyphens."
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

        <SectionDivider label="Slack appearance" />

        <Field
          label="Slack display name"
          hint="shown when the agent posts in Slack. optional — defaults to 'relay'."
          error={errorField === "slack_display_name" ? error : null}
        >
          <input
            type="text"
            value={slackDisplayName}
            onChange={(e) => setSlackDisplayName(e.target.value)}
            className="rl-input"
            placeholder="Alfred"
            disabled={submitting}
            maxLength={30}
          />
        </Field>

        <Field
          label="Icon"
          hint="optional · :emoji: or upload an image"
          error={errorField === "slack_icon_url" ? error : null}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 8,
              flexWrap: "wrap",
            }}
          >
            <IconKindToggle
              active={iconKind === "emoji"}
              onClick={() => {
                setIconKind("emoji");
                setPendingFile(null);
                if (pendingPreview) URL.revokeObjectURL(pendingPreview);
                setPendingPreview(null);
              }}
              disabled={submitting}
            >
              <Smile size={13} /> Emoji
            </IconKindToggle>
            <IconKindToggle
              active={iconKind === "file"}
              onClick={() => fileInputRef.current?.click()}
              disabled={submitting}
            >
              <ImageIcon size={13} /> Upload image
            </IconKindToggle>
            {(iconKind !== "none" || pendingFile) && (
              <button
                type="button"
                onClick={onClearIcon}
                disabled={submitting}
                style={{
                  background: "transparent",
                  border: 0,
                  color: "var(--color-fg3)",
                  fontSize: 12,
                  padding: "4px 8px",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <X size={12} /> Clear
              </button>
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/gif"
            onChange={onPickFile}
            disabled={submitting}
            style={{ display: "none" }}
          />

          {iconKind === "emoji" && (
            <input
              type="text"
              value={iconEmoji}
              onChange={(e) => setIconEmoji(e.target.value.toLowerCase())}
              className="rl-input"
              placeholder=":robot_face:"
              disabled={submitting}
              maxLength={64}
              pattern=":[a-z0-9_+\-]+:"
            />
          )}

          {iconKind === "file" && (pendingFile || iconUrl) && (
            <div
              style={{
                fontSize: 12,
                color: "var(--color-fg3)",
                padding: "6px 10px",
                background: "var(--color-surface)",
                border: "1px solid var(--color-border-subtle)",
                borderRadius: "var(--radius-sm)",
              }}
            >
              {pendingFile
                ? `Will upload on save: ${pendingFile.name} (${(pendingFile.size / 1024).toFixed(0)} KB)`
                : "Using the previously uploaded image."}
            </div>
          )}
        </Field>

        <PersonaPreview
          displayName={slackDisplayName}
          slug={slug}
          iconEmoji={iconKind === "emoji" ? iconEmoji : ""}
          iconUrl={pendingPreview ?? (iconKind === "file" ? iconUrl : null)}
        />

        <SectionDivider />

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
// Persona section helpers
// ---------------------------------------------------------------------------

function SectionDivider({ label }: { label?: string }) {
  if (!label) {
    return (
      <hr
        style={{
          border: 0,
          borderTop: "1px solid var(--color-border-subtle)",
          margin: "20px 0 8px",
        }}
      />
    );
  }
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        margin: "20px 0 14px",
      }}
    >
      <span
        style={{
          fontSize: 11,
          color: "var(--color-fg3)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          fontFamily: "var(--font-mono)",
        }}
      >
        {label}
      </span>
      <div
        style={{
          flex: 1,
          height: 1,
          background: "var(--color-border-subtle)",
        }}
      />
    </div>
  );
}

function IconKindToggle({
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
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "6px 12px",
        fontSize: 13,
        fontFamily: "inherit",
        background: active ? "var(--color-accent-tint)" : "var(--color-surface)",
        color: active ? "var(--color-accent)" : "var(--color-fg2)",
        border: `1px solid ${active ? "var(--color-accent-ring)" : "var(--color-border)"}`,
        borderRadius: "var(--radius-sm)",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "background 120ms var(--ease-std)",
      }}
    >
      {children}
    </button>
  );
}

/**
 * Faux Slack message header showing how the bot will appear when it posts.
 * Renders the display name (falls back to slug, then "relay") + the avatar.
 */
function PersonaPreview({
  displayName,
  slug,
  iconEmoji,
  iconUrl,
}: {
  displayName: string;
  slug: string;
  iconEmoji: string;
  iconUrl: string | null;
}) {
  const name = displayName.trim() || slug.trim() || "relay";
  const showAvatar = !!(iconEmoji || iconUrl);

  return (
    <div
      style={{
        marginBottom: 16,
        padding: "12px 14px",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "var(--radius-sm)",
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          color: "var(--color-fg3)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          fontFamily: "var(--font-mono)",
          marginBottom: 8,
        }}
      >
        Slack preview
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 6,
            background: showAvatar ? "transparent" : "var(--color-accent-tint)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
            border: "1px solid var(--color-border-subtle)",
            flexShrink: 0,
          }}
        >
          {iconUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={iconUrl}
              alt=""
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : iconEmoji ? (
            <span style={{ fontSize: 14, fontFamily: "var(--font-mono)" }}>
              {iconEmoji}
            </span>
          ) : (
            <span
              style={{
                fontWeight: 600,
                fontSize: 14,
                color: "var(--color-accent)",
              }}
            >
              {name.slice(0, 1).toUpperCase()}
            </span>
          )}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--color-fg1)" }}>
              {name}
            </span>
            <span
              style={{
                fontSize: 10,
                padding: "1px 5px",
                background: "var(--color-fg4)",
                color: "var(--color-fg-inv)",
                borderRadius: 3,
                fontFamily: "var(--font-mono)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                fontWeight: 500,
              }}
            >
              APP
            </span>
            <span style={{ fontSize: 11, color: "var(--color-fg3)" }}>
              just now
            </span>
          </div>
          <div
            style={{
              fontSize: 13,
              color: "var(--color-fg2)",
              marginTop: 2,
              lineHeight: 1.4,
            }}
          >
            <em style={{ color: "var(--color-fg3)" }}>
              How this agent will appear when it replies in Slack.
            </em>
          </div>
        </div>
      </div>
    </div>
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
        <RichAgentSelect
          agents={agents}
          value={anthropicAgentId}
          onChange={onPickAgent}
          disabled={disabled}
          error={errorField === "anthropic_agent_id"}
        />
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

/**
 * Two-tier dropdown for the CMA agents list. Native <select> can't render
 * multi-line styled options, so this is a small custom popover — friendly
 * description (first line of the system prompt) on top, model + agent_id
 * in smaller mono text underneath.
 *
 * Click-outside + Esc both close it. Keyboard nav (arrow keys) is
 * deferred — most users browse with the mouse here and the dialog has
 * other inputs that need keyboard focus.
 */
function RichAgentSelect({
  agents,
  value,
  onChange,
  disabled,
  error,
}: {
  agents: CmaAgentSummary[];
  value: string;
  onChange: (id: string) => void;
  disabled: boolean;
  error: boolean;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const selected = agents.find((a) => a.id === value) ?? null;

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => !disabled && setOpen((v) => !v)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        style={{
          width: "100%",
          textAlign: "left",
          padding: "10px 12px",
          background: "var(--color-surface)",
          border: `1px solid ${error ? "var(--color-danger-border)" : "var(--color-border)"}`,
          borderRadius: "var(--radius-sm)",
          fontSize: 13,
          fontFamily: "inherit",
          cursor: disabled ? "not-allowed" : "pointer",
          display: "flex",
          alignItems: "center",
          gap: 8,
          color: "var(--color-fg1)",
          minHeight: 48,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          {selected ? (
            <>
              <RichLine main>
                {preview(selected.system, 80) || selected.model || selected.id}
              </RichLine>
              <RichLine>
                {selected.model
                  ? `${selected.model}  ·  ${selected.id}`
                  : selected.id}
              </RichLine>
            </>
          ) : (
            <span style={{ color: "var(--color-fg3)" }}>Pick an agent…</span>
          )}
        </div>
        <ChevronDown
          size={14}
          style={{ color: "var(--color-fg3)", flexShrink: 0 }}
        />
      </button>

      {open && (
        <div
          role="listbox"
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            maxHeight: 320,
            overflowY: "auto",
            background: "var(--color-surface-2)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            boxShadow:
              "0 4px 12px rgb(0 0 0 / 0.08), 0 1px 3px rgb(0 0 0 / 0.04)",
            zIndex: 50,
          }}
        >
          {agents.map((a, idx) => {
            const isSelected = a.id === value;
            return (
              <button
                type="button"
                key={a.id}
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange(a.id);
                  setOpen(false);
                }}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "10px 12px",
                  background: isSelected
                    ? "var(--color-accent-tint)"
                    : "transparent",
                  border: 0,
                  borderTop:
                    idx === 0
                      ? "none"
                      : "1px solid var(--color-border-subtle)",
                  fontFamily: "inherit",
                  cursor: "pointer",
                  color: "var(--color-fg1)",
                  transition: "background 80ms var(--ease-std)",
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = "var(--color-surface-3)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = "transparent";
                  }
                }}
              >
                <RichLine main bold={isSelected}>
                  {preview(a.system, 100) || a.model || a.id}
                </RichLine>
                <RichLine>
                  {a.model ? `${a.model}  ·  ${a.id}` : a.id}
                </RichLine>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function RichLine({
  children,
  main,
  bold,
}: {
  children: React.ReactNode;
  main?: boolean;
  bold?: boolean;
}) {
  return (
    <div
      style={{
        fontSize: main ? 13 : 11,
        color: main ? "var(--color-fg1)" : "var(--color-fg3)",
        fontFamily: main ? "inherit" : "var(--font-mono)",
        fontWeight: bold ? 500 : 400,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        lineHeight: 1.4,
        marginTop: main ? 0 : 2,
      }}
    >
      {children}
    </div>
  );
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
  slug: { field: "slug", message: "name must start with a letter and use only lowercase/digits/hyphens" },
  invalid_slug: { field: "slug", message: "name must start with a letter and use only lowercase/digits/hyphens" },
  slug_in_use: { field: "slug", message: "an active agent already uses this name" },
  anthropic_agent_id: { field: "anthropic_agent_id", message: "anthropic_agent_id required" },
  environment_id: { field: "environment_id", message: "environment_id required" },
  archived: { field: "general", message: "this agent is archived — restore it first" },
  slack_display_name_in_use: {
    field: "slack_display_name",
    message: "another active agent already uses that Slack display name",
  },
  too_large: {
    field: "slack_icon_url",
    message: "icon is too large — keep it under 1 MB",
  },
  bad_image_type: {
    field: "slack_icon_url",
    message: "icon must be a PNG, JPEG, or GIF",
  },
  bad_image: {
    field: "slack_icon_url",
    message: "that file isn't a valid image — try a different one",
  },
  storage_error: {
    field: "slack_icon_url",
    message: "couldn't save the icon — try again or pick another image",
  },
};
