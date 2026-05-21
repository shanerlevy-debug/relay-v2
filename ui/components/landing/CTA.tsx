import Link from "next/link";

/**
 * Final CTA. Centered, light-mode, single primary action.
 */
export function CTA() {
  return (
    <section
      className="rl-section"
      style={{
        background: "var(--color-surface)",
        borderBottom: "none",
        padding: "100px 32px",
        textAlign: "center",
      }}
    >
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <div className="rl-eyebrow" style={{ marginBottom: 16 }}>
          Two minutes to wired
        </div>
        <h2 className="rl-h2" style={{ marginBottom: 20 }}>
          The next thread isn&apos;t going to <em>wait.</em>
        </h2>
        <p
          style={{
            fontSize: 17,
            lineHeight: 1.55,
            color: "var(--color-fg3)",
            marginBottom: 32,
          }}
        >
          Sign up, install Relay in your Slack workspace, paste your Anthropic key,
          and the next time someone needs an answer in #help they&apos;ll have one
          before they finish typing the question.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <Link href="/signup" className="rl-btn rl-btn-primary rl-btn-lg">
            Create your workspace
          </Link>
          <Link href="/login" className="rl-btn rl-btn-ghost rl-btn-lg">
            Sign in →
          </Link>
        </div>
      </div>
    </section>
  );
}
