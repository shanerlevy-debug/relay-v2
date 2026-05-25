import Link from "next/link";

import { ArrowRight, CheckCircle2, KeyRound, MessageSquareDashed, Slack, UsersRound } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { getMe, serverFetch } from "@/lib/api";

interface AnthropicKeyStatus {
  has_key: boolean;
  created_at: string | null;
  updated_at: string | null;
  created_by_user_id: string | null;
}

interface AgentSeats {
  active: number;
  cap: number;
}

interface AgentListOut {
  agents: unknown[];
  seats: AgentSeats;
}

interface UserSeats {
  active: number;
  pending_invites: number;
  cap: number;
}

interface UserListOut {
  users: unknown[];
  seats: UserSeats;
}

/**
 * Home (workspace overview). Server-side fetches all four cards in parallel.
 * The data shape mirrors the FastAPI endpoints in
 * api/relay_api/routes/{workspace,agents,users}.py.
 */
export default async function HomePage() {
  const [session, anthropicKey, agentList, userList] = await Promise.all([
    getMe(),
    serverFetch<AnthropicKeyStatus>("/api/workspace/anthropic-key"),
    serverFetch<AgentListOut>("/api/agents"),
    serverFetch<UserListOut>("/api/users"),
  ]);

  const slackConnected = !!session.workspace.slack_team_id;
  const isAdmin = session.user.role === "admin";
  const firstName = session.user.email.split("@")[0].split(".")[0];

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div
          className="rl-eyebrow"
          style={{ color: "var(--color-fg3)", marginBottom: 8 }}
        >
          {session.workspace.display_name}
        </div>
        <h1
          style={{
            margin: 0,
            fontSize: 28,
            fontWeight: 600,
            letterSpacing: "-0.015em",
            lineHeight: 1.15,
          }}
        >
          Good to see you, {firstName}.
        </h1>
      </div>

      {/* Link-your-Slack banner — shown until the user has completed
          Slack OIDC sign-in at least once. Without it, the bot can't
          recognize them and will reject their messages. */}
      {session.user.slack_user_verified_at == null && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "12px 14px",
            background: "var(--color-accent-tint)",
            border: "1px solid var(--color-accent-ring)",
            borderRadius: "var(--radius-sm)",
            marginBottom: 18,
            fontSize: 13,
            color: "var(--color-fg2)",
          }}
        >
          <Slack size={18} style={{ color: "var(--color-accent)", flexShrink: 0 }} />
          <div style={{ flex: 1, lineHeight: 1.5 }}>
            <strong style={{ color: "var(--color-fg1)" }}>
              Link your Slack account
            </strong>{" "}
            so the bot can recognize you. Without this, your messages to
            <span className="mono"> @relay</span> in Slack will be rejected.
          </div>
          <a
            href="/api/oauth/slack-signin/start"
            className="rl-btn rl-btn-primary"
            style={{ fontSize: 12, padding: "6px 12px", flexShrink: 0 }}
          >
            Sign in with Slack
            <ArrowRight size={12} />
          </a>
        </div>
      )}

      {/* Top row — setup state */}
      <div className="rl-home-cards" style={{ marginBottom: 16 }}>
        <SetupCard
          icon={<Slack size={18} />}
          title="Slack workspace"
          connected={slackConnected}
          connectedLabel={`Connected · ${session.workspace.display_name}`}
          ctaHref="/settings"
          ctaLabel={isAdmin ? "Connect Slack" : "Ask an admin"}
          ctaEnabled={isAdmin}
          notConfiguredBody="Install Relay to a Slack workspace. Two-minute OAuth flow."
        />

        <SetupCard
          icon={<KeyRound size={18} />}
          title="Anthropic API key"
          connected={anthropicKey.has_key}
          connectedLabel={
            anthropicKey.created_at
              ? `Set ${formatDate(anthropicKey.created_at)}`
              : "Configured"
          }
          ctaHref="/settings"
          ctaLabel={isAdmin ? "Add Anthropic key" : "Ask an admin"}
          ctaEnabled={isAdmin}
          notConfiguredBody="Required to invoke any agent. Paste your sk-ant- key in Settings."
        />
      </div>

      {/* Bottom row — counts */}
      <div className="rl-home-cards">
        <CountCard
          icon={<MessageSquareDashed size={18} />}
          title="Agents"
          primary={`${agentList.seats.active} / ${agentList.seats.cap}`}
          subtext="active in this workspace"
          ctaHref="/agents"
          ctaLabel="Manage agents"
        />

        <CountCard
          icon={<UsersRound size={18} />}
          title="Users"
          primary={`${userList.seats.active} / ${userList.seats.cap}`}
          subtext={
            userList.seats.pending_invites > 0
              ? `${userList.seats.pending_invites} pending invite${userList.seats.pending_invites === 1 ? "" : "s"}`
              : "active in this workspace"
          }
          ctaHref="/users"
          ctaLabel={isAdmin ? "Manage users" : "View users"}
        />
      </div>

      {/* Pointer to the audit log */}
      <div style={{ marginTop: 28, fontSize: 13 }}>
        <Link href="/audit" className="link mono-xs">
          See recent activity in the audit log →
        </Link>
      </div>
    </>
  );
}

function SetupCard({
  icon,
  title,
  connected,
  connectedLabel,
  ctaHref,
  ctaLabel,
  ctaEnabled,
  notConfiguredBody,
}: {
  icon: React.ReactNode;
  title: string;
  connected: boolean;
  connectedLabel: string;
  ctaHref: string;
  ctaLabel: string;
  ctaEnabled: boolean;
  notConfiguredBody: string;
}) {
  return (
    <Card padding={20}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            background: connected
              ? "var(--color-success-tint)"
              : "var(--color-accent-tint)",
            color: connected ? "var(--color-success)" : "var(--color-accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {icon}
        </div>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{title}</h2>
      </div>

      {connected ? (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 13.5,
              color: "var(--color-success)",
              fontWeight: 500,
              marginBottom: 4,
            }}
          >
            <CheckCircle2 size={14} />
            {connectedLabel}
          </div>
          <Link
            href={ctaHref}
            className="link mono-xs"
            style={{ textDecoration: "none", fontSize: 11 }}
          >
            Manage in Settings →
          </Link>
        </>
      ) : (
        <>
          <p
            style={{
              fontSize: 13.5,
              color: "var(--color-fg3)",
              lineHeight: 1.5,
              margin: "0 0 12px",
            }}
          >
            {notConfiguredBody}
          </p>
          {ctaEnabled ? (
            <Link
              href={ctaHref}
              className="rl-btn rl-btn-primary"
              style={{ fontSize: 12, padding: "6px 12px" }}
            >
              {ctaLabel}
              <ArrowRight size={12} />
            </Link>
          ) : (
            <span className="mono-xs">{ctaLabel}</span>
          )}
        </>
      )}
    </Card>
  );
}

function CountCard({
  icon,
  title,
  primary,
  subtext,
  ctaHref,
  ctaLabel,
}: {
  icon: React.ReactNode;
  title: string;
  primary: string;
  subtext: string;
  ctaHref: string;
  ctaLabel: string;
}) {
  return (
    <Card padding={20}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 6,
            background: "var(--color-muted-tint)",
            color: "var(--color-fg2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {icon}
        </div>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{title}</h2>
      </div>

      <div
        style={{
          fontSize: 26,
          fontWeight: 600,
          letterSpacing: "-0.02em",
          lineHeight: 1.1,
          fontFamily: "var(--font-mono)",
        }}
      >
        {primary}
      </div>
      <div style={{ marginTop: 4, marginBottom: 12, fontSize: 12, color: "var(--color-fg3)" }}>
        {subtext}
      </div>

      <Link
        href={ctaHref}
        className="link mono-xs"
        style={{ textDecoration: "none", fontSize: 11 }}
      >
        {ctaLabel} →
      </Link>
    </Card>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
