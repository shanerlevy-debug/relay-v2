import {
  KeyRound,
  ScrollText,
  ShieldCheck,
  Shuffle,
  Sparkles,
  UsersRound,
} from "lucide-react";
import type { ComponentType } from "react";

/**
 * Six-cell feature grid. Pop-up-scoped — each feature reflects what we
 * actually ship (not the mockup's enterprise framing).
 */
const features: Array<{
  Icon: ComponentType<{ size?: number }>;
  title: string;
  body: string;
}> = [
  {
    Icon: KeyRound,
    title: "Bring your own Anthropic key",
    body: "You pay Anthropic directly — we just route. Keys are AES-256-GCM-enveloped at rest, decrypted only when a message routes.",
  },
  {
    Icon: ShieldCheck,
    title: "Slack-native auth",
    body: "Every install is a real Slack OAuth — workspace-scoped, signed by Slack. No shared bot tokens, no secrets baked into env.",
  },
  {
    Icon: Shuffle,
    title: "Slug-based agent routing",
    body: "Address agents by name — @relay vanguard or /relay alfred. Thread context keeps follow-ups with the same agent.",
  },
  {
    Icon: Sparkles,
    title: "Up to 25 agents per workspace",
    body: "Mix Sonnet, Opus, Haiku — your call. Each agent has its own slug, system prompt, and env.",
  },
  {
    Icon: ScrollText,
    title: "Audit log built in",
    body: "Every routed message becomes a row — who, when, which agent, which channel, which Claude session. Searchable from day one.",
  },
  {
    Icon: UsersRound,
    title: "Up to 25 users",
    body: "Email invites, admin + member roles. When you outgrow it, Powerloom is right next door — same team, no re-platforming.",
  },
];

export function Features() {
  return (
    <section
      id="features"
      className="rl-section"
      style={{ background: "var(--color-surface-2)" }}
    >
      <div className="rl-section-inner">
        <div className="rl-eyebrow">What you get</div>
        <h2 className="rl-h2" style={{ marginTop: 14, marginBottom: 56, maxWidth: 780 }}>
          A thin <em>relay,</em> not another platform.
        </h2>

        <div
          className="rl-features-grid"
          style={{
            background: "var(--color-border)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          {features.map(({ Icon, title, body }) => (
            <div
              key={title}
              style={{
                background: "var(--color-surface)",
                padding: "32px 28px",
                display: "flex",
                flexDirection: "column",
                gap: 14,
              }}
            >
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 6,
                  background: "var(--color-surface-3)",
                  color: "var(--color-accent)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon size={20} />
              </div>
              <h3
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  margin: 0,
                  letterSpacing: "-0.01em",
                }}
              >
                {title}
              </h3>
              <p
                style={{
                  fontSize: 13.5,
                  lineHeight: 1.55,
                  color: "var(--color-fg3)",
                  margin: 0,
                }}
              >
                {body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
