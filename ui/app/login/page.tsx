import Link from "next/link";

import { RelayMark } from "@/components/RelayMark";

/**
 * Login page placeholder. Real form wires to POST /api/auth/login in
 * the next commit (needs the `lib/api.ts` typed fetch wrapper).
 */
export default function LoginPage() {
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
            Email
          </label>
          <input
            type="email"
            className="rl-input"
            placeholder="you@company.com"
            disabled
          />
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
          Sign in
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
          <a href="#" className="link">
            Forgot password
          </a>
          <Link href="/signup" className="link">
            Sign up →
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
          form wires to POST /api/auth/login next commit
        </p>
      </div>
    </div>
  );
}
