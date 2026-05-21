import { CheckCircle2, Slack } from "lucide-react";

import type { WorkspaceOut } from "@/lib/api";

/**
 * Slack integration panel.
 *
 * Not connected: 'Connect Slack' button -> regular <a> to
 *   /api/oauth/slack/start which 303s to slack.com's authorize page.
 * Connected: green check + team name + audit hint. Revoke flow is
 *   deferred to a polish pass (no DELETE endpoint exposed yet).
 */
export function SlackPanel({
  workspace,
  isAdmin,
}: {
  workspace: WorkspaceOut;
  isAdmin: boolean;
}) {
  const connected = !!workspace.slack_team_id;

  return (
    <section
      style={{
        background: "var(--color-surface-2)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        padding: 24,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            background: "#4A154B",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Slack size={16} />
        </div>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Slack integration</h2>
      </div>

      {connected ? (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 14,
              color: "var(--color-success)",
              fontWeight: 500,
              marginBottom: 6,
            }}
          >
            <CheckCircle2 size={15} />
            Connected · team {workspace.slack_team_id}
          </div>
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--color-fg3)", lineHeight: 1.55 }}>
            Bot token encrypted at rest. Reconnect from your workspace admin to revoke;
            in-product disconnect lands with the next polish pass.
          </p>
        </>
      ) : (
        <>
          <p
            style={{
              margin: 0,
              marginBottom: 14,
              fontSize: 13.5,
              color: "var(--color-fg2)",
              lineHeight: 1.55,
            }}
          >
            Install Relay to a Slack workspace. Two-minute OAuth flow — pick the workspace,
            authorize the bot scopes, and you&apos;re wired.
          </p>
          {isAdmin ? (
            <a
              href="/api/oauth/slack/start"
              className="rl-btn rl-btn-primary"
              style={{ textDecoration: "none" }}
            >
              <Slack size={14} />
              Connect Slack
            </a>
          ) : (
            <span className="mono-xs">Ask your workspace admin to connect Slack.</span>
          )}
        </>
      )}
    </section>
  );
}
