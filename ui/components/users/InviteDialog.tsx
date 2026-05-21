"use client";

import { Check, Copy } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Dialog } from "@/components/ui/Dialog";
import {
  ApiError,
  InviteCreateResponse,
  inviteUser,
} from "@/lib/api";

const FIELD_ERRORS: Record<string, { field?: "email" | "role"; message: string }> = {
  email_in_use: {
    field: "email",
    message: "This email is already registered with a Relay account.",
  },
  invite_already_pending: {
    field: "email",
    message: "This email already has a pending invite — revoke it first to re-send.",
  },
  invalid_email: { field: "email", message: "Email format looks off." },
  invalid_role: { field: "role", message: "Role must be admin or member." },
};

/**
 * Invite a teammate. Two-phase UX:
 *   Phase A: form (email + role). On success →
 *   Phase B: "Invite sent — copy the link" confirmation with the raw
 *            invite URL (since Resend isn't wired in v1, the admin
 *            shares the link manually).
 */
export function InviteDialog({
  open,
  onClose,
  onSent,
  onLimitHit,
}: {
  open: boolean;
  onClose: () => void;
  onSent: () => Promise<void> | void;
  onLimitHit: () => void;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "member">("member");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorField, setErrorField] = useState<string | null>(null);
  const [result, setResult] = useState<InviteCreateResponse | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;
    setEmail("");
    setRole("member");
    setSubmitting(false);
    setError(null);
    setErrorField(null);
    setResult(null);
    setCopied(false);
  }, [open]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setErrorField(null);
    try {
      const res = await inviteUser({ email: email.trim(), role });
      setResult(res);
      await onSent();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "user_limit_reached") {
          // Hand off to the LimitHitDialog at the page level.
          onLimitHit();
          onClose();
          return;
        }
        const mapped = FIELD_ERRORS[err.code];
        setError(mapped?.message ?? err.message);
        setErrorField(mapped?.field ?? null);
      } else {
        setError("Something went wrong. Try again.");
      }
      setSubmitting(false);
    }
  }

  async function onCopy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.invite_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API blocked — user can select + copy manually.
    }
  }

  // Phase B: invite created, show share-link confirmation
  if (result) {
    return (
      <Dialog
        open={open}
        onClose={onClose}
        title="Invite sent ✓"
        description={`${result.invite.email} will receive an email shortly. While we wire Resend, share the link manually:`}
        maxWidth={520}
      >
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "stretch",
            marginBottom: 16,
          }}
        >
          <input
            type="text"
            readOnly
            value={result.invite_url}
            className="rl-input mono"
            style={{ fontSize: 12, flex: 1 }}
            onFocus={(e) => e.target.select()}
          />
          <button
            type="button"
            onClick={onCopy}
            className="rl-btn rl-btn-secondary"
            style={{ flexShrink: 0 }}
          >
            {copied ? (
              <>
                <Check size={14} />
                Copied
              </>
            ) : (
              <>
                <Copy size={14} />
                Copy
              </>
            )}
          </button>
        </div>

        <p
          style={{
            fontSize: 12,
            color: "var(--color-fg3)",
            margin: 0,
            marginBottom: 20,
          }}
        >
          Expires {new Date(result.invite.expires_at).toLocaleString()}.
          {result.invite.role === "admin"
            ? " The recipient will join as an admin."
            : " The recipient will join as a member."}
        </p>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button onClick={onClose} className="rl-btn rl-btn-primary">
            Done
          </button>
        </div>
      </Dialog>
    );
  }

  // Phase A: form
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Invite a teammate"
      description="They'll get a link to set their password and join the workspace."
      maxWidth={460}
    >
      <form onSubmit={onSubmit}>
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
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rl-input"
            placeholder="name@company.com"
            required
            autoFocus
            disabled={submitting}
          />
          {errorField === "email" && error && (
            <div style={{ fontSize: 12, color: "var(--color-danger)", marginTop: 4 }}>
              {error}
            </div>
          )}
        </div>

        <div style={{ marginBottom: 20 }}>
          <label
            style={{
              display: "block",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--color-fg2)",
              marginBottom: 8,
            }}
          >
            Role
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <RoleOption
              checked={role === "member"}
              onChange={() => setRole("member")}
              title="Member"
              body="Can use Slack agents and view workspace settings."
              disabled={submitting}
            />
            <RoleOption
              checked={role === "admin"}
              onChange={() => setRole("admin")}
              title="Admin"
              body="Manages agents, users, Slack install, and the Anthropic key."
              disabled={submitting}
            />
          </div>
        </div>

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
            {submitting ? "Sending…" : "Send invite"}
          </button>
        </div>

        <p
          style={{
            marginTop: 18,
            fontSize: 11,
            color: "var(--color-fg4)",
            fontFamily: "var(--font-mono)",
            textAlign: "center",
          }}
        >
          email send wires in week 3 alongside Resend — for now, share the link manually
        </p>
      </form>
    </Dialog>
  );
}

function RoleOption({
  checked,
  onChange,
  title,
  body,
  disabled,
}: {
  checked: boolean;
  onChange: () => void;
  title: string;
  body: string;
  disabled: boolean;
}) {
  return (
    <label
      style={{
        display: "flex",
        gap: 10,
        padding: "10px 12px",
        background: checked ? "var(--color-accent-tint)" : "var(--color-surface)",
        border: `1px solid ${checked ? "var(--color-accent)" : "var(--color-border)"}`,
        borderRadius: "var(--radius-sm)",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "background 120ms, border-color 120ms",
        alignItems: "flex-start",
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <input
        type="radio"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        style={{ marginTop: 3 }}
      />
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: checked ? "var(--color-accent)" : "var(--color-fg1)",
          }}
        >
          {title}
        </div>
        <div style={{ fontSize: 12, color: "var(--color-fg3)", marginTop: 2 }}>{body}</div>
      </div>
    </label>
  );
}
