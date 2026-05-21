import { ArrowUpRight } from "lucide-react";

/**
 * Free-plan card with the Enterprise upsell. The deliberate-ceiling
 * shows up here as a feature: "Need more? Talk to us about Enterprise."
 */
export function PlanPanel() {
  return (
    <section
      style={{
        background: "var(--color-surface-2)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        padding: 24,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div>
          <h2 style={{ margin: 0, marginBottom: 6, fontSize: 15, fontWeight: 600 }}>
            Plan
          </h2>
          <p
            style={{
              margin: 0,
              fontSize: 14,
              color: "var(--color-fg1)",
              fontWeight: 500,
            }}
          >
            Free · BYOK · 25 users · 25 agents
          </p>
          <p
            style={{
              margin: "8px 0 0",
              fontSize: 12.5,
              color: "var(--color-fg3)",
              lineHeight: 1.55,
              maxWidth: 520,
            }}
          >
            Need SSO, multi-workspace, per-channel RBAC, SOC2, multi-AZ SLA, or more than
            25 of anything? Talk to us about Enterprise — same team, built for the next
            stage.
          </p>
        </div>
        <a
          href="https://powerloom.dev"
          target="_blank"
          rel="noreferrer"
          className="rl-btn rl-btn-secondary"
        >
          Talk to Enterprise
          <ArrowUpRight size={13} />
        </a>
      </div>
    </section>
  );
}
