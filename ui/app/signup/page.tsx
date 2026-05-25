"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { GoogleSignInButton } from "@/components/GoogleSignInButton";
import { RelayMark } from "@/components/RelayMark";
import { SlackSignInButton } from "@/components/SlackSignInButton";
import { ApiError, signup } from "@/lib/api";

const SLACK_BANNER_MESSAGES: Record<string, string> = {
  email_unavailable:
    "Slack didn't share an email for your account. Sign up here and you can connect Slack from Settings after.",
  error:
    "Something went wrong installing from Slack. Sign up here and try connecting from Settings.",
};

const ERROR_MESSAGES: Record<string, { field?: "email" | "password" | "workspace_name"; message: string }> = {
  email_in_use: {
    field: "email",
    message: "An account with this email already exists. Try signing in.",
  },
  invalid_email: {
    field: "email",
    message: "Email format looks off — double-check.",
  },
  weak_password: {
    field: "password",
    message: "Use 12 or more characters.",
  },
  invalid_workspace_name: {
    field: "workspace_name",
    message: "Workspace name can't be empty.",
  },
};

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupPageInner />
    </Suspense>
  );
}

function SignupPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const slackFlag = searchParams.get("slack");
  const slackBanner = slackFlag ? SLACK_BANNER_MESSAGES[slackFlag] : null;

  const [workspaceName, setWorkspaceName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorField, setErrorField] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setErrorField(null);
    try {
      await signup({
        workspace_name: workspaceName,
        email,
        password,
      });
      router.push("/home");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        const known = ERROR_MESSAGES[err.code];
        setError(known?.message ?? err.message);
        setErrorField(known?.field ?? null);
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
          relay
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
          maxWidth: 420,
        }}
      >
        <h1
          style={{
            margin: 0,
            fontSize: 22,
            fontWeight: 600,
            letterSpacing: "-0.015em",
            marginBottom: 8,
          }}
        >
          Create your workspace
        </h1>
        <p
          style={{
            fontSize: 13,
            color: "var(--color-fg3)",
            margin: 0,
            marginBottom: 24,
          }}
        >
          Free up to 25 users and 25 agents. BYO Anthropic key.
        </p>

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

        <div style={{ marginBottom: 10 }}>
          <SlackSignInButton variant="dark" label="Sign up with Slack" />
        </div>
        <div style={{ marginBottom: 16 }}>
          <GoogleSignInButton label="Sign up with Google" />
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
          <span>or with email</span>
          <div style={{ flex: 1, height: 1, background: "var(--color-border)" }} />
        </div>

        <Field label="Workspace name" htmlFor="ws_name" error={errorField === "workspace_name" ? error : null}>
          <input
            id="ws_name"
            type="text"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
            className="rl-input"
            placeholder="Acme"
            required
            autoFocus
            disabled={submitting}
            minLength={2}
            maxLength={255}
          />
        </Field>

        <Field label="Your email" htmlFor="email" error={errorField === "email" ? error : null}>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rl-input"
            placeholder="you@company.com"
            required
            disabled={submitting}
          />
        </Field>

        <Field
          label="Password"
          htmlFor="password"
          hint="12+ characters"
          error={errorField === "password" ? error : null}
        >
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rl-input"
            placeholder="••••••••••••"
            required
            minLength={12}
            disabled={submitting}
          />
        </Field>

        {error && errorField === null && (
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

        <button
          type="submit"
          className="rl-btn rl-btn-primary"
          style={{ width: "100%", justifyContent: "center" }}
          disabled={submitting}
        >
          {submitting ? "Creating…" : "Create workspace"}
        </button>

        <div
          style={{
            marginTop: 20,
            paddingTop: 20,
            borderTop: "1px solid var(--color-border-subtle)",
            textAlign: "center",
            fontSize: 13,
          }}
        >
          Already have an account?{" "}
          <Link href="/login" className="link">
            Sign in
          </Link>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string | null;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label
        htmlFor={htmlFor}
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
        <div style={{ fontSize: 12, color: "var(--color-danger)", marginTop: 6 }}>
          {error}
        </div>
      )}
    </div>
  );
}
