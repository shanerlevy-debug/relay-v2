import { ArrowUpRight } from "lucide-react";

/**
 * The "graduate to Powerloom" callout. Lives between the feature grid
 * and the final CTA. This is where the deliberate-ceiling-as-feature
 * shows up — we list what Powerloom adds, so prospects with bigger needs
 * route themselves there cleanly.
 */
export function PowerloomCallout() {
  return (
    <section
      className="rl-section"
      style={{
        background: "rgb(var(--ink-900))",
        color: "rgb(var(--paper-50))",
        padding: "72px 32px",
        borderBottom: "none",
      }}
    >
      <div className="rl-section-inner rl-callout-grid">
        <div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "rgb(var(--thread-300))",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              marginBottom: 14,
            }}
          >
            ↑ from the Powerloom team
          </div>
          <h2
            style={{
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.025em",
              lineHeight: 1.15,
              margin: "0 0 14px",
              maxWidth: 720,
            }}
          >
            Relay is the bridge.{" "}
            <em
              style={{
                fontFamily: "var(--font-serif)",
                fontStyle: "italic",
                fontWeight: 500,
              }}
            >
              Powerloom is the platform.
            </em>
          </h2>
          <p
            style={{
              fontSize: 16,
              lineHeight: 1.55,
              color: "rgb(var(--ink-100))",
              margin: 0,
              maxWidth: 640,
            }}
          >
            When 25 agents and 25 users isn&apos;t enough: SSO, multi-workspace
            orgs, per-channel RBAC, approval flows, audit-chain integrity, a
            memory stack, an MCP fleet, SOC2-ready audit retention. Same team,
            same conventions, no re-platforming.
          </p>
        </div>
        <a
          href="https://powerloom.dev"
          className="rl-callout-cta"
          style={{
            padding: "14px 22px",
            background: "rgb(var(--thread-500))",
            color: "#fff",
            borderRadius: 4,
            fontSize: 14,
            fontWeight: 500,
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            whiteSpace: "nowrap",
          }}
        >
          See Powerloom
          <ArrowUpRight size={14} />
        </a>
      </div>
    </section>
  );
}
