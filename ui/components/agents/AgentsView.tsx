"use client";

import { Archive, Bot, Pencil, Plus, Star } from "lucide-react";
import { useEffect, useState } from "react";

import { AgentDialog } from "@/components/agents/AgentDialog";
import { LimitHitDialog } from "@/components/agents/LimitHitDialog";
import { GroupChips } from "@/components/groups/GroupChips";
import { Card } from "@/components/ui/Card";
import {
  AgentListOut,
  AgentOut,
  ApiError,
  archiveAgent,
  getGroupMemberships,
  GroupMembershipMap,
  GroupSummary,
  listAgents,
} from "@/lib/api";

/**
 * Main client-side view for /agents.
 *
 * Receives initial data from the server component. After mutations we
 * re-fetch the full list to keep the seat count + default flag in sync
 * (cheap — max 25 rows).
 */
interface AgentsViewProps {
  initial: AgentListOut;
  isAdmin: boolean;
}

export function AgentsView({ initial, isAdmin }: AgentsViewProps) {
  const [data, setData] = useState<AgentListOut>(initial);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<AgentOut | null>(null);
  const [limitHit, setLimitHit] = useState(false);
  const [topError, setTopError] = useState<string | null>(null);

  // Group memberships are fetched once on mount + refreshed alongside the
  // agents list. Held in a flat map keyed by agent id; missing keys mean
  // "no groups" (which renders as nothing rather than a "loading" state
  // to avoid layout shift).
  const [memberships, setMemberships] = useState<GroupMembershipMap | null>(null);

  useEffect(() => {
    let cancelled = false;
    getGroupMemberships()
      .then((m) => { if (!cancelled) setMemberships(m); })
      .catch(() => { /* non-fatal — chips just stay empty */ });
    return () => { cancelled = true; };
  }, []);

  async function refresh() {
    try {
      const [next, m] = await Promise.all([
        listAgents(),
        getGroupMemberships().catch(() => null),
      ]);
      setData(next);
      if (m) setMemberships(m);
    } catch (err) {
      setTopError(err instanceof Error ? err.message : "Failed to reload agents.");
    }
  }

  function groupsForAgent(agentId: string): GroupSummary[] {
    return memberships?.agents[agentId] ?? [];
  }

  function openCreate() {
    if (data.seats.active >= data.seats.cap) {
      setLimitHit(true);
      return;
    }
    setCreating(true);
  }

  async function onArchive(agent: AgentOut) {
    if (!confirm(`Archive ${agent.slug}? Active threads pinned to this agent will route to the default on next reply.`)) {
      return;
    }
    try {
      await archiveAgent(agent.id);
      await refresh();
    } catch (err) {
      setTopError(err instanceof Error ? err.message : "Failed to archive agent.");
    }
  }

  return (
    <>
      {/* Header */}
      <div className="rl-page-header">
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: 24,
              fontWeight: 600,
              letterSpacing: "-0.015em",
            }}
          >
            Agents
          </h1>
          <p
            style={{
              margin: "6px 0 0",
              fontSize: 13,
              color: "var(--color-fg3)",
            }}
          >
            Address each agent in Slack as <span className="mono">@relay &lt;name&gt;</span>.
            Set one as the default for untagged messages.
          </p>
        </div>
        <div className="rl-page-header-actions">
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              color: data.seats.active >= data.seats.cap ? "var(--color-danger)" : "var(--color-fg3)",
            }}
          >
            {data.seats.active} of {data.seats.cap}
          </span>
          {isAdmin && (
            <button onClick={openCreate} className="rl-btn rl-btn-primary">
              <Plus size={14} />
              New agent
            </button>
          )}
        </div>
      </div>

      {topError && (
        <div
          style={{
            padding: "10px 12px",
            background: "var(--color-danger-tint)",
            border: "1px solid var(--color-danger-border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--color-danger)",
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          {topError}{" "}
          <button
            onClick={() => setTopError(null)}
            style={{
              background: "transparent",
              border: 0,
              color: "var(--color-danger)",
              textDecoration: "underline",
              cursor: "pointer",
              fontFamily: "inherit",
              fontSize: 13,
              marginLeft: 6,
            }}
          >
            dismiss
          </button>
        </div>
      )}

      {/* Empty state */}
      {data.agents.length === 0 ? (
        <Card padding={48} style={{ textAlign: "center" }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "50%",
              background: "var(--color-accent-tint)",
              color: "var(--color-accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
            }}
          >
            <Bot size={22} />
          </div>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>No agents yet</h2>
          <p
            style={{
              margin: "6px 0 16px",
              fontSize: 13,
              color: "var(--color-fg3)",
              maxWidth: 360,
              marginLeft: "auto",
              marginRight: "auto",
            }}
          >
            Add an agent to give your team a name like{" "}
            <span className="mono">@relay alfred ping</span>.
          </p>
          {isAdmin && (
            <button onClick={openCreate} className="rl-btn rl-btn-primary">
              <Plus size={14} />
              Add your first agent
            </button>
          )}
        </Card>
      ) : (
        /* Table */
        <div className="rl-table rl-table-stack-on-mobile">
          {/* Header row */}
          <div
            className="rl-table-head"
            style={{
              display: "grid",
              gridTemplateColumns: "1.2fr 2fr 100px 150px",
              alignItems: "center",
            }}
          >
            <div>Name</div>
            <div>Description</div>
            <div>Default</div>
            <div />
          </div>

          {data.agents.map((agent) => (
            <AgentRow
              key={agent.id}
              agent={agent}
              isAdmin={isAdmin}
              onEdit={() => setEditing(agent)}
              onArchive={() => onArchive(agent)}
              groups={groupsForAgent(agent.id)}
            />
          ))}
        </div>
      )}

      {/* Dialogs */}
      <AgentDialog
        open={creating}
        onClose={() => setCreating(false)}
        onSaved={async () => {
          await refresh();
        }}
      />

      <AgentDialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        editing={editing}
        onSaved={async () => {
          await refresh();
        }}
      />

      <LimitHitDialog
        open={limitHit}
        onClose={() => setLimitHit(false)}
        context="agent_limit"
        cap={data.seats.cap}
      />
    </>
  );
}

function AgentRow({
  agent,
  isAdmin,
  onEdit,
  onArchive,
  groups,
}: {
  agent: AgentOut;
  isAdmin: boolean;
  onEdit: () => void;
  onArchive: () => void;
  groups: GroupSummary[];
}) {
  return (
    <div
      className="rl-table-row"
      style={{
        display: "grid",
        gridTemplateColumns: "1.2fr 2fr 100px 150px",
        alignItems: "center",
      }}
    >
      <div>
        <div className="mono" style={{ fontSize: 13, fontWeight: 500, color: "var(--color-fg1)" }}>
          {agent.slug}
        </div>
        <div className="mono-xs" style={{ marginTop: 2 }}>
          {agent.anthropic_agent_id}
        </div>
      </div>
      <div style={{ color: "var(--color-fg2)", fontSize: 13 }}>
        <div>
          {agent.description || (
            <span style={{ color: "var(--color-fg4)" }}>—</span>
          )}
        </div>
        {groups.length > 0 && (
          <div style={{ marginTop: 4 }}>
            <GroupChips groups={groups} />
          </div>
        )}
      </div>
      <div>
        {agent.is_default ? (
          <span className="rl-badge rl-badge-accent">
            <Star size={10} fill="currentColor" />
            default
          </span>
        ) : null}
      </div>
      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
        {isAdmin && (
          <>
            <button
              onClick={onEdit}
              className="rl-btn rl-btn-ghost"
              style={{ padding: "5px 10px", fontSize: 12 }}
              title="Edit agent"
            >
              <Pencil size={12} />
              Edit
            </button>
            <button
              onClick={onArchive}
              className="rl-btn rl-btn-ghost"
              style={{
                padding: "5px 10px",
                fontSize: 12,
                color: "var(--color-fg3)",
              }}
              title="Archive agent"
            >
              <Archive size={12} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
