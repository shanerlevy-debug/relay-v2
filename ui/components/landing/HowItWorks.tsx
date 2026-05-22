import { CheckCircle2, KeyRound, MessageSquare } from "lucide-react";

/**
 * The "three pieces" section. Pop-up-scoped — signup → BYOK + Slack →
 * /relay it. No per-channel binding, no "bind agents" enterprise flow.
 */
export function HowItWorks() {
  return (
    <section id="how" className="rl-section" style={{ background: "var(--color-surface)" }}>
      <div className="rl-section-inner">
        <div className="rl-eyebrow">How it works</div>
        <h2 className="rl-h2" style={{ marginTop: 14, marginBottom: 24, maxWidth: 780 }}>
          Three pieces. <em>That&apos;s it.</em>
        </h2>
        <p
          style={{
            fontSize: 17,
            lineHeight: 1.55,
            color: "var(--color-fg3)",
            maxWidth: 620,
            marginBottom: 56,
          }}
        >
          You bring the Slack workspace and the Anthropic key. Relay does the boring middle.
        </p>

        <div className="rl-grid-3">
          <Step
            n="01"
            title="Create your workspace"
            body="Sign up with email + password, then install Relay to Slack via OAuth. Two minutes, no service-account dance."
            visual={<SlackInstallVisual />}
          />
          <Step
            n="02"
            title="Paste your Anthropic key"
            body="Drop your sk-ant-… key into Settings. Envelope-encrypted at rest (AES-256-GCM). Your spend, your control."
            visual={<KeyVisual />}
          />
          <Step
            n="03"
            title="@relay it"
            body="Add agents by name — up to 25 per workspace. Mention @relay or /relay <name> anywhere in Slack; replies post back in the thread."
            visual={<ThreadVisual />}
          />
        </div>
      </div>
    </section>
  );
}

function Step({
  n,
  title,
  body,
  visual,
}: {
  n: string;
  title: string;
  body: string;
  visual: React.ReactNode;
}) {
  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--color-fg3)",
          letterSpacing: "0.12em",
          marginBottom: 8,
        }}
      >
        STEP {n}
      </div>
      <h3
        style={{
          fontSize: 24,
          fontWeight: 600,
          letterSpacing: "-0.015em",
          margin: "0 0 10px",
          color: "var(--color-fg1)",
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: 14.5,
          lineHeight: 1.6,
          color: "var(--color-fg3)",
          margin: "0 0 20px",
          minHeight: 70,
        }}
      >
        {body}
      </p>
      <div
        style={{
          background: "var(--color-surface-2)",
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          padding: 16,
          minHeight: 180,
          position: "relative",
          overflow: "hidden",
        }}
      >
        {visual}
      </div>
    </div>
  );
}

function SlackInstallVisual() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        style={{
          padding: "10px 12px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 4,
            background: "#4A154B",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            fontSize: 14,
          }}
        >
          #
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 500 }}>Acme Robotics</div>
          <div className="mono-xs" style={{ fontSize: 10.5 }}>
            acme.slack.com
          </div>
        </div>
        <CheckCircle2 size={14} color="var(--color-success)" />
      </div>
      <div
        style={{
          padding: "8px 12px",
          background: "var(--color-accent-tint)",
          border: "1px solid var(--color-accent)",
          borderRadius: 6,
          color: "var(--color-accent)",
          fontSize: 12,
          fontWeight: 500,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
        }}
      >
        Connect Slack
      </div>
      <div
        style={{
          fontSize: 11,
          color: "var(--color-fg3)",
          textAlign: "center",
          marginTop: 4,
          fontFamily: "var(--font-mono)",
        }}
      >
        OAuth · ~2 minutes
      </div>
    </div>
  );
}

function KeyVisual() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, justifyContent: "center", height: "100%" }}>
      <div
        style={{
          padding: "14px 14px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 6,
            background: "var(--color-accent-tint)",
            color: "var(--color-accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <KeyRound size={18} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 500 }}>Anthropic API key</div>
          <div
            className="mono-xs"
            style={{
              fontSize: 11,
              marginTop: 2,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            sk-ant-•••••••••••••••••
          </div>
        </div>
        <div
          className="rl-badge rl-badge-success"
          style={{ fontSize: 10, padding: "2px 6px" }}
        >
          <span className="rl-dot" />
          set
        </div>
      </div>
      <div
        style={{
          fontSize: 11,
          color: "var(--color-fg3)",
          textAlign: "center",
          fontFamily: "var(--font-mono)",
        }}
      >
        envelope-encrypted · never echoed
      </div>
    </div>
  );
}

function ThreadVisual() {
  return (
    <div style={{ fontSize: 12, lineHeight: 1.5 }}>
      <div style={{ marginBottom: 10 }}>
        <span style={{ fontWeight: 700, fontSize: 12.5 }}>maya </span>
        <span className="mono-xs" style={{ fontSize: 10.5 }}>
          10:43
        </span>
        <div style={{ marginTop: 2 }}>
          <span
            style={{
              background: "var(--color-accent-tint)",
              color: "var(--color-accent)",
              padding: "1px 5px",
              borderRadius: 3,
              fontFamily: "var(--font-mono)",
              fontSize: 11.5,
            }}
          >
            /relay runbook investigate
          </span>
        </div>
      </div>
      <div
        style={{
          borderLeft: "2px solid var(--color-accent)",
          paddingLeft: 12,
          marginLeft: 4,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 12.5, color: "var(--color-accent)" }}>
          Relay · @runbook{" "}
        </span>
        <span className="mono-xs" style={{ fontSize: 10.5 }}>
          10:48
        </span>
        <div style={{ marginTop: 2, color: "var(--color-fg2)" }}>
          <MessageSquare size={11} style={{ display: "inline", verticalAlign: -1 }} />{" "}
          Likely cause: deploy{" "}
          <span
            className="mono"
            style={{
              background: "var(--color-surface)",
              padding: "0 4px",
              borderRadius: 3,
              fontSize: 11,
            }}
          >
            4a8c2e1
          </span>{" "}
          at 10:38…
        </div>
      </div>
    </div>
  );
}
