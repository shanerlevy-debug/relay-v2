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

      {/* Top row — setup state */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 16,
        }}
      >
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
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
        }}
      >
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

      {/* Audit / Activity preview — coming with the audit endpoint */}
      <div style={{ marginTop: 32, color: "var(--color-fg3)", fontSize: 13 }}>
        <span className="mono-xs">/api/audit endpoint + recent activity feed land in the next commit.</span>
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
