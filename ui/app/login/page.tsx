"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { RelayMark } from "@/components/RelayMark";
import { ApiError, login } from "@/lib/api";

const SLACK_BANNER_MESSAGES: Record<string, string> = {
  email_in_use:
    "An account with this Slack email already exists. Sign in here, then connect Slack from Settings.",
  team_already_connected:
    "This Slack workspace is already connected to a Relay account. Sign in below.",
};

export default function LoginPage() {
  // useSearchParams forces a CSR bailout for static prerender — wrap the
  // real component in a Suspense boundary so /login still prerenders.
  return (
    <Suspense fallback={null}>
      <LoginPageInner />
    </Suspense>
  );
}

function LoginPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const slackFlag = searchParams.get("slack");
  const slackBanner = slackFlag ? SLACK_BANNER_MESSAGES[slackFlag] : null;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setErrorCode(null);
    try {
      await login({ email, password });
      router.push("/home");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        // Don't leak which field was wrong — the API uses the same code for
        // unknown email + wrong password.
        setError("Email or password is incorrect.");
        setErrorCode(err.code);
      } else {
        setError("Something went wrong. Please try again.");
      }
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 32,
        background: "var(--color-surface)",
      }}
    >
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 32 }}>
        <RelayMark size={36} />
        <span
          style={{
            fontSize: 20,
            fontWeight: 600,
            letterSpacing: "-0.01em",
            color: "var(--color-fg1)",
          }}
        >
          Relay
        </span>
      </Link>

      <form
        onSubmit={onSubmit}
        style={{
          background: "var(--color-surface-2)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          padding: 32,
          width: "100%",
          maxWidth: 380,
        }}
      >
        <h1
          style={{
            margin: 0,
            fontSize: 22,
            fontWeight: 600,
            letterSpacing: "-0.015em",
            marginBottom: 24,
          }}
        >
          Welcome back
        </h1>

        {slackBanner && (
          <div
            style={{
              padding: "10px 12px",
              background: "var(--color-relay-tint, rgba(255, 138, 95, 0.08))",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-fg2)",
              fontSize: 13,
              lineHeight: 1.4,
              marginBottom: 16,
            }}
          >
            {slackBanner}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <GoogleSignInButton />
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            margin: "20px 0",
            color: "var(--color-fg3)",
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          <div style={{ flex: 1, height: 1, background: "var(--color-border)" }} />
          <span>or</span>
          <div style={{ flex: 1, height: 1, background: "var(--color-border)" }} />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label
            htmlFor="email"
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
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rl-input"
            placeholder="you@company.com"
            required
            autoFocus
            disabled={submitting}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label
            htmlFor="password"
            style={{
              display: "block",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--color-fg2)",
              marginBottom: 6,
            }}
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rl-input"
            placeholder="••••••••••••"
            required
            disabled={submitting}
          />
        </div>

        {error && (
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
            {errorCode && (
              <span className="mono-xs" style={{ color: "var(--color-fg4)", marginLeft: 6 }}>
                ({errorCode})
              </span>
            )}
          </div>
        )}

        <button
          type="submit"
          className="rl-btn rl-btn-primary"
          style={{ width: "100%", justifyContent: "center" }}
          disabled={submitting}
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>

        <div
          style={{
            marginTop: 20,
            paddingTop: 20,
            borderTop: "1px solid var(--color-border-subtle)",
            display: "flex",
            justifyContent: "space-between",
            fontSize: 13,
          }}
        >
          <span style={{ color: "var(--color-fg4)" }}>Forgot password</span>
          <Link href="/signup" className="link">
            Sign up →
          </Link>
        </div>
      </form>
    </div>
  );
}
