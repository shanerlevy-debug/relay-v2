import Link from "next/link";

import { RelayMark } from "@/components/RelayMark";

/**
 * Signup page placeholder. Mirrors /login's centered-card pattern. The
 * form wires to POST /api/auth/signup in the next commit (along with
 * lib/api.ts + the auth flow).
 */
export default function SignupPage() {
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
      <Link
        href="/"
        style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 32 }}
      >
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

      <div
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

        <div style={{ marginBottom: 16 }}>
          <label
            style={{
              display: "block",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--color-fg2)",
              marginBottom: 6,
            }}
          >
            Workspace name
          </label>
          <input type="text" className="rl-input" placeholder="Acme" disabled />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label
            style={{
              display: "block",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--color-fg2)",
              marginBottom: 6,
            }}
          >
            Your email
          </label>
          <input type="email" className="rl-input" placeholder="you@company.com" disabled />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label
            style={{
              display: "block",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--color-fg2)",
              marginBottom: 6,
            }}
          >
            Password
            <span
              style={{
                fontWeight: 400,
                color: "var(--color-fg3)",
                marginLeft: 6,
                fontSize: 11,
              }}
            >
              12+ characters
            </span>
          </label>
          <input
            type="password"
            className="rl-input"
            placeholder="••••••••••••"
            disabled
          />
        </div>

        <button
          className="rl-btn rl-btn-primary"
          style={{ width: "100%", justifyContent: "center" }}
          disabled
        >
          Create workspace
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

        <p
          className="mono-xs"
          style={{
            marginTop: 24,
            textAlign: "center",
            color: "var(--color-fg4)",
          }}
        >
          form wires to POST /api/auth/signup next commit
        </p>
      </div>
    </div>
  );
}
