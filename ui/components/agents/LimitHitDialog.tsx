"use client";

import { ArrowUpRight } from "lucide-react";

import { Dialog } from "@/components/ui/Dialog";

/**
 * Modal that fires when an admin tries to create a 26th agent (or
 * invite a 26th user — same component, reused for both).
 *
 * The deliberate-ceiling-as-a-feature: list what Enterprise unlocks,
 * make it look like an upgrade path, not a wall.
 */
interface LimitHitDialogProps {
  open: boolean;
  onClose: () => void;
  /** Distinguishes the messaging — agent limit vs user limit. */
  context: "agent_limit" | "user_limit";
  /** What the cap was set to (so the message is concrete). */
  cap: number;
}

const COPY: Record<LimitHitDialogProps["context"], { title: string; subtitle: string }> = {
  agent_limit: {
    title: "Workspace is at the agent limit",
    subtitle: "You're using every seat. Archive one, or unlock more in Enterprise.",
  },
  user_limit: {
    title: "Workspace is at the user limit",
    subtitle: "Free up a seat by removing a user, or unlock more in Enterprise.",
  },
};

const ENTERPRISE_FEATURES = [
  "More than 25 users + 25 agents",
  "SSO (SAML/OIDC)",
  "Per-channel + per-user permissions",
  "SOC2 + audit-chain integrity",
  "99.9% multi-AZ SLA",
  "Memory store + skills + MCP fleet",
];

export function LimitHitDialog({ open, onClose, context, cap }: LimitHitDialogProps) {
  const copy = COPY[context];

  return (
    <Dialog open={open} onClose={onClose} title={`${copy.title} (${cap})`} description={copy.subtitle} maxWidth={520}>
      <div
        style={{
          padding: "16px 18px",
          background: "var(--color-accent-tint)",
          border: "1px solid var(--color-accent)",
          borderRadius: "var(--radius-lg)",
          marginBottom: 20,
        }}
      >
        <div
          className="rl-eyebrow"
          style={{ color: "var(--color-accent)", marginBottom: 10 }}
        >
          Enterprise unlocks
        </div>
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "8px 16px",
          }}
        >
          {ENTERPRISE_FEATURES.map((f) => (
            <li
              key={f}
              style={{
                fontSize: 12.5,
                color: "var(--color-fg1)",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span
                style={{
                  width: 4,
                  height: 4,
                  borderRadius: "50%",
                  background: "var(--color-accent)",
                  flexShrink: 0,
                }}
              />
              {f}
            </li>
          ))}
        </ul>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <button onClick={onClose} className="rl-btn rl-btn-ghost">
          Keep using Free
        </button>
        <a
          href="https://powerloom.dev"
          target="_blank"
          rel="noreferrer"
          className="rl-btn rl-btn-primary"
        >
          Talk to us about Enterprise
          <ArrowUpRight size={13} />
        </a>
      </div>
    </Dialog>
  );
}
