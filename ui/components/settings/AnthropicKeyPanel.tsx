"use client";

import { CheckCircle2, Eye, EyeOff, KeyRound } from "lucide-react";
import { FormEvent, useState } from "react";

import {
  AnthropicKeyStatus,
  ApiError,
  deleteAnthropicKey,
  getAnthropicKeyStatus,
  setAnthropicKey,
} from "@/lib/api";

/**
 * BYOK Anthropic key panel.
 *
 * Not set / replacing: paste form with show-hide toggle. Validated
 *   client-side for sk-ant- prefix before submit.
 * Set: green confirmation + replace + remove buttons.
 */
export function AnthropicKeyPanel({
  initial,
  isAdmin,
}: {
  initial: AnthropicKeyStatus;
  isAdmin: boolean;
}) {
  const [status, setStatus] = useState<AnthropicKeyStatus>(initial);
  const [mode, setMode] = useState<"display" | "edit">(initial.has_key ? "display" : "edit");
  const [keyValue, setKeyValue] = useState("");
  const [show, setShow] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setStatus(await getAnthropicKeyStatus());
    } catch {
      // Tolerate refresh failures — user can reload.
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const trimmed = keyValue.trim();
    if (!trimmed.startsWith("sk-ant-")) {
      setError("Anthropic keys start with sk-ant-.");
      setSubmitting(false);
      return;
    }
    try {
      const next = await setAnthropicKey(trimmed);
      setStatus(next);
      setKeyValue("");
      setShow(false);
      setMode("display");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong. Try again.");
      }
      setSubmitting(false);
      return;
    }
    setSubmitting(false);
  }

  async function onRemove() {
    if (!confirm("Remove the Anthropic key? The bridge will reply with an error to any message until a new key is set.")) {
      return;
    }
    setSubmitting(true);
    try {
      await deleteAnthropicKey();
      await refresh();
      setMode("edit");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove key.");
    }
    setSubmitting(false);
  }

  return (
    <section
      style={{
        background: "var(--color-surface-2)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        padding: 24,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            background: "var(--color-accent-tint)",
            color: "var(--color-accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <KeyRound size={16} />
        </div>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Anthropic API key</h2>
      </div>

      {status.has_key && mode === "display" ? (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 14,
              color: "var(--color-success)",
              fontWeight: 500,
              marginBottom: 4,
            }}
          >
            <CheckCircle2 size={15} />
            Configured
            {status.created_at && (
              <span
                style={{
                  fontWeight: 400,
                  color: "var(--color-fg3)",
                  marginLeft: 4,
                  fontSize: 13,
                }}
              >
                · set {formatDate(status.created_at)}
              </span>
            )}
          </div>
          <p
            style={{
              margin: 0,
              marginBottom: 16,
              fontSize: 12.5,
              color: "var(--color-fg3)",
              lineHeight: 1.55,
            }}
          >
            Encrypted at rest with AES-256-GCM, decrypted just-in-time when the bridge
            invokes an agent. The key value is never echoed by the API.
          </p>
          {isAdmin && (
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => {
                  setMode("edit");
                  setError(null);
                  setKeyValue("");
                }}
                className="rl-btn rl-btn-secondary"
                disabled={submitting}
              >
                Replace key
              </button>
              <button
                onClick={onRemove}
                className="rl-btn rl-btn-ghost"
                disabled={submitting}
                style={{ color: "var(--color-danger)" }}
              >
                Remove
              </button>
            </div>
          )}
        </>
      ) : (
        <>
          {!isAdmin ? (
            <p style={{ margin: 0, fontSize: 13, color: "var(--color-fg3)" }}>
              Ask your workspace admin to set the Anthropic key.
            </p>
          ) : (
            <form onSubmit={onSubmit}>
              <p
                style={{
                  margin: 0,
                  marginBottom: 12,
                  fontSize: 13,
                  color: "var(--color-fg3)",
                  lineHeight: 1.55,
                }}
              >
                Paste your <span className="mono">sk-ant-…</span> key from{" "}
                <a
                  href="https://console.anthropic.com/settings/keys"
                  target="_blank"
                  rel="noreferrer"
                  className="link"
                >
                  console.anthropic.com
                </a>
                . Encrypted on save, never shown again.
              </p>

              <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                <div style={{ flex: 1, position: "relative" }}>
                  <input
                    type={show ? "text" : "password"}
                    value={keyValue}
                    onChange={(e) => setKeyValue(e.target.value)}
                    className="rl-input mono"
                    placeholder="sk-ant-api03-…"
                    required
                    autoFocus
                    minLength={10}
                    maxLength={512}
                    disabled={submitting}
                    style={{ paddingRight: 36, fontSize: 13 }}
                  />
                  <button
                    type="button"
                    onClick={() => setShow((s) => !s)}
                    aria-label={show ? "Hide key" : "Show key"}
                    style={{
                      position: "absolute",
                      right: 6,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      padding: 6,
                      color: "var(--color-fg3)",
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    {show ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              {error && (
                <div
                  style={{
                    padding: "8px 12px",
                    background: "var(--color-danger-tint)",
                    border: "1px solid var(--color-danger-border)",
                    borderRadius: "var(--radius-sm)",
                    color: "var(--color-danger)",
                    fontSize: 13,
                    marginBottom: 12,
                  }}
                >
                  {error}
                </div>
              )}

              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="submit"
                  className="rl-btn rl-btn-primary"
                  disabled={submitting || !keyValue.trim()}
                >
                  {submitting ? "Saving…" : status.has_key ? "Save new key" : "Save key"}
                </button>
                {status.has_key && (
                  <button
                    type="button"
                    onClick={() => {
                      setMode("display");
                      setKeyValue("");
                      setError(null);
                    }}
                    className="rl-btn rl-btn-ghost"
                    disabled={submitting}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          )}
        </>
      )}
    </section>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
