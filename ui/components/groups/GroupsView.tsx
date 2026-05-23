"use client";

import {
  Bot,
  Plus,
  Shield,
  ShieldCheck,
  Trash2,
  UserMinus,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Card } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import {
  addAgentToGroup,
  addUserToGroup,
  ApiError,
  archiveGroup,
  createGroup,
  getGroup,
  GroupListOut,
  GroupMemberAgent,
  GroupMembersOut,
  GroupMemberUser,
  GroupOut,
  listAgents,
  listUsers,
  removeAgentFromGroup,
  removeUserFromGroup,
  renameGroup,
  UserListOut,
  AgentListOut,
} from "@/lib/api";

/**
 * /groups view — list groups on the left, detail (members + agents) on
 * the right. Members and agents are managed inline via add-pickers.
 *
 * Design decisions per Shane's signoff (2026-05-23):
 *   - Default group can be renamed but not archived.
 *   - No deny rules — adding to a group grants access; removing revokes.
 *   - When removing the default group from an agent, confirm because it
 *     downgrades reachability for everyone not in another group.
 */
export function GroupsView({ initial }: { initial: GroupListOut }) {
  const [groups, setGroups] = useState<GroupOut[]>(initial.groups);
  const [selectedId, setSelectedId] = useState<string | null>(
    initial.groups[0]?.id ?? null,
  );
  const [detail, setDetail] = useState<GroupMembersOut | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [topError, setTopError] = useState<string | null>(null);

  // Fetch detail whenever selection changes.
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    getGroup(selectedId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (cancelled) return;
        setTopError(
          err instanceof Error ? err.message : "Failed to load group.",
        );
        setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  async function refreshGroups() {
    // We don't have a re-list helper exposed; the simplest re-fetch is to
    // re-mount detail — but if the user just created/archived a group we
    // also want to update the sidebar. So we re-pull the list via apiFetch.
    try {
      const resp = await fetch("/api/groups", { credentials: "include" });
      if (resp.ok) {
        const next = (await resp.json()) as GroupListOut;
        setGroups(next.groups);
      }
    } catch {
      // non-fatal
    }
  }

  async function refreshDetail() {
    if (!selectedId) return;
    try {
      const d = await getGroup(selectedId);
      setDetail(d);
    } catch (err) {
      setTopError(
        err instanceof Error ? err.message : "Failed to refresh group.",
      );
    }
  }

  async function onArchive(group: GroupOut) {
    if (group.is_default) return;
    if (
      !confirm(
        `Archive "${group.name}"? Members of this group lose access to its agents (unless they share another group with the agent).`,
      )
    ) {
      return;
    }
    try {
      await archiveGroup(group.id);
      const next = groups.filter((g) => g.id !== group.id);
      setGroups(next);
      setSelectedId(next[0]?.id ?? null);
    } catch (err) {
      setTopError(
        err instanceof Error ? err.message : "Failed to archive group.",
      );
    }
  }

  return (
    <>
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
            Groups
          </h1>
          <p
            style={{
              margin: "6px 0 0",
              fontSize: 13,
              color: "var(--color-fg3)",
            }}
          >
            A user can talk to an agent when they share at least one group.
            The default group is the catch-all — everyone starts in it; new
            agents start in it.
          </p>
        </div>
        <div className="rl-page-header-actions">
          <button
            onClick={() => setCreating(true)}
            className="rl-btn rl-btn-primary"
          >
            <Plus size={14} />
            New group
          </button>
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

      <div className="rl-groups-grid">
        <GroupList
          groups={groups}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onArchive={onArchive}
        />

        <div>
          {!detail && !detailLoading && (
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
                <Shield size={22} />
              </div>
              <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
                Pick a group
              </h2>
              <p
                style={{
                  margin: "6px 0 0",
                  fontSize: 13,
                  color: "var(--color-fg3)",
                  maxWidth: 360,
                  marginLeft: "auto",
                  marginRight: "auto",
                }}
              >
                Or create one above. Most workspaces only need a few — the
                default + a small group per team that needs a private agent.
              </p>
            </Card>
          )}

          {detailLoading && !detail && (
            <Card padding={48} style={{ textAlign: "center" }}>
              <div style={{ color: "var(--color-fg3)", fontSize: 13 }}>
                Loading…
              </div>
            </Card>
          )}

          {detail && (
            <GroupDetail
              detail={detail}
              onRenamed={async (next) => {
                setDetail(next);
                await refreshGroups();
              }}
              onMembershipChanged={async () => {
                await refreshDetail();
              }}
              onError={(msg) => setTopError(msg)}
            />
          )}
        </div>
      </div>

      <CreateGroupDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={async (g) => {
          await refreshGroups();
          setSelectedId(g.id);
          setCreating(false);
        }}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Sidebar — group list
// ---------------------------------------------------------------------------

function GroupList({
  groups,
  selectedId,
  onSelect,
  onArchive,
}: {
  groups: GroupOut[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onArchive: (g: GroupOut) => void;
}) {
  return (
    <div
      style={{
        background: "var(--color-surface-2)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
      }}
    >
      {groups.map((g, idx) => {
        const isSel = g.id === selectedId;
        return (
          <button
            key={g.id}
            onClick={() => onSelect(g.id)}
            type="button"
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "12px 14px",
              background: isSel ? "var(--color-accent-tint)" : "transparent",
              border: 0,
              borderTop: idx === 0 ? "none" : "1px solid var(--color-border-subtle)",
              fontSize: 14,
              fontFamily: "inherit",
              cursor: "pointer",
              color: "var(--color-fg1)",
              position: "relative",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span
                style={{
                  fontWeight: isSel ? 500 : 400,
                  flex: 1,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {g.name}
              </span>
              {g.is_default && (
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: "var(--font-mono)",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    padding: "1px 6px",
                    background: "var(--color-accent-tint)",
                    color: "var(--color-accent)",
                    borderRadius: 3,
                    fontWeight: 500,
                  }}
                >
                  Default
                </span>
              )}
              {!g.is_default && isSel && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onArchive(g);
                  }}
                  style={{
                    background: "transparent",
                    border: 0,
                    color: "var(--color-fg3)",
                    cursor: "pointer",
                    padding: 2,
                  }}
                  title="Archive group"
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail pane — members + agents
// ---------------------------------------------------------------------------

function GroupDetail({
  detail,
  onRenamed,
  onMembershipChanged,
  onError,
}: {
  detail: GroupMembersOut;
  onRenamed: (next: GroupMembersOut) => Promise<void>;
  onMembershipChanged: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(detail.group.name);
  const [addingUser, setAddingUser] = useState(false);
  const [addingAgent, setAddingAgent] = useState(false);

  useEffect(() => {
    setNameDraft(detail.group.name);
    setEditingName(false);
  }, [detail.group.id]);

  async function saveName() {
    const next = nameDraft.trim();
    if (!next || next === detail.group.name) {
      setEditingName(false);
      setNameDraft(detail.group.name);
      return;
    }
    try {
      const updated = await renameGroup(detail.group.id, next);
      await onRenamed({ ...detail, group: updated });
      setEditingName(false);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Failed to rename group.");
    }
  }

  async function removeUser(u: GroupMemberUser) {
    try {
      await removeUserFromGroup(detail.group.id, u.id);
      await onMembershipChanged();
    } catch (err) {
      onError(
        err instanceof Error ? err.message : "Failed to remove member.",
      );
    }
  }

  async function removeAgent(a: GroupMemberAgent) {
    if (
      detail.group.is_default &&
      !confirm(
        `Remove "${a.slack_display_name || a.slug}" from the default group? Workspace members without explicit group access won't be able to reach it.`,
      )
    ) {
      return;
    }
    try {
      await removeAgentFromGroup(detail.group.id, a.id);
      await onMembershipChanged();
    } catch (err) {
      onError(
        err instanceof Error ? err.message : "Failed to remove agent.",
      );
    }
  }

  return (
    <div
      style={{
        background: "var(--color-surface-2)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        padding: 20,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 8,
        }}
      >
        {detail.group.is_default ? (
          <ShieldCheck size={18} style={{ color: "var(--color-accent)" }} />
        ) : (
          <Shield size={18} style={{ color: "var(--color-fg3)" }} />
        )}
        {editingName ? (
          <input
            type="text"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            onBlur={saveName}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveName();
              if (e.key === "Escape") {
                setEditingName(false);
                setNameDraft(detail.group.name);
              }
            }}
            className="rl-input"
            style={{ fontSize: 18, fontWeight: 600, flex: 1 }}
            autoFocus
            maxLength={64}
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditingName(true)}
            style={{
              background: "transparent",
              border: 0,
              padding: 0,
              fontSize: 18,
              fontWeight: 600,
              color: "var(--color-fg1)",
              cursor: "text",
              fontFamily: "inherit",
              letterSpacing: "-0.01em",
            }}
            title="Click to rename"
          >
            {detail.group.name}
          </button>
        )}
        {detail.group.is_default && (
          <span
            style={{
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              padding: "1px 6px",
              background: "var(--color-accent-tint)",
              color: "var(--color-accent)",
              borderRadius: 3,
              fontWeight: 500,
            }}
          >
            Default
          </span>
        )}
      </div>

      {/* Members section */}
      <Section
        title="Members"
        count={detail.users.length}
        icon={<Users size={14} />}
        onAdd={() => setAddingUser(true)}
        addLabel="Add user"
      >
        {detail.users.length === 0 ? (
          <EmptyState text="No members in this group." />
        ) : (
          <Rows>
            {detail.users.map((u) => (
              <Row key={u.id}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: "var(--color-fg1)" }}>
                    {u.email}
                  </div>
                  <div className="mono-xs" style={{ marginTop: 2 }}>
                    {u.role}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => removeUser(u)}
                  className="rl-btn rl-btn-ghost"
                  style={{ padding: "4px 8px", fontSize: 12 }}
                  title="Remove from group"
                >
                  <UserMinus size={12} />
                </button>
              </Row>
            ))}
          </Rows>
        )}
      </Section>

      {/* Agents section */}
      <Section
        title="Agents"
        count={detail.agents.length}
        icon={<Bot size={14} />}
        onAdd={() => setAddingAgent(true)}
        addLabel="Add agent"
      >
        {detail.agents.length === 0 ? (
          <EmptyState text="No agents in this group." />
        ) : (
          <Rows>
            {detail.agents.map((a) => (
              <Row key={a.id}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: "var(--color-fg1)" }}>
                    {a.slack_display_name ?? a.slug}
                  </div>
                  <div className="mono-xs" style={{ marginTop: 2 }}>
                    @relay {a.slug}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => removeAgent(a)}
                  className="rl-btn rl-btn-ghost"
                  style={{ padding: "4px 8px", fontSize: 12 }}
                  title="Remove from group"
                >
                  <X size={12} />
                </button>
              </Row>
            ))}
          </Rows>
        )}
      </Section>

      <AddMemberDialog
        open={addingUser}
        onClose={() => setAddingUser(false)}
        kind="user"
        groupId={detail.group.id}
        existingIds={new Set(detail.users.map((u) => u.id))}
        onAdded={async () => {
          setAddingUser(false);
          await onMembershipChanged();
        }}
      />

      <AddMemberDialog
        open={addingAgent}
        onClose={() => setAddingAgent(false)}
        kind="agent"
        groupId={detail.group.id}
        existingIds={new Set(detail.agents.map((a) => a.id))}
        onAdded={async () => {
          setAddingAgent(false);
          await onMembershipChanged();
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add user / add agent dialog — single component, kind-switched
// ---------------------------------------------------------------------------

function AddMemberDialog({
  open,
  onClose,
  kind,
  groupId,
  existingIds,
  onAdded,
}: {
  open: boolean;
  onClose: () => void;
  kind: "user" | "agent";
  groupId: string;
  existingIds: Set<string>;
  onAdded: () => Promise<void>;
}) {
  const [users, setUsers] = useState<UserListOut["users"]>([]);
  const [agents, setAgents] = useState<AgentListOut["agents"]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const promise = kind === "user" ? listUsers() : listAgents();
    promise
      .then((r) => {
        if (cancelled) return;
        if (kind === "user") setUsers((r as UserListOut).users);
        else setAgents((r as AgentListOut).agents);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, kind]);

  const candidates = useMemo(() => {
    if (kind === "user") {
      return users
        .filter((u) => !existingIds.has(u.id))
        .map((u) => ({ id: u.id, label: u.email, sub: u.role }));
    }
    return agents
      .filter((a) => !existingIds.has(a.id))
      .map((a) => ({
        id: a.id,
        label: a.slack_display_name ?? a.slug,
        sub: `@relay ${a.slug}`,
      }));
  }, [kind, users, agents, existingIds]);

  async function pick(id: string) {
    setSubmitting(true);
    setError(null);
    try {
      if (kind === "user") await addUserToGroup(groupId, id);
      else await addAgentToGroup(groupId, id);
      await onAdded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={kind === "user" ? "Add user to group" : "Add agent to group"}
      description={
        candidates.length === 0
          ? "Everyone's already a member."
          : "Pick one to add."
      }
      maxWidth={420}
    >
      {error && (
        <div
          style={{
            padding: "10px 12px",
            background: "var(--color-danger-tint)",
            border: "1px solid var(--color-danger-border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--color-danger)",
            fontSize: 13,
            marginBottom: 12,
          }}
        >
          {error}
        </div>
      )}
      {loading ? (
        <div style={{ color: "var(--color-fg3)", fontSize: 13, padding: "16px 0" }}>
          Loading…
        </div>
      ) : candidates.length === 0 ? null : (
        <div
          style={{
            maxHeight: 340,
            overflowY: "auto",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
          }}
        >
          {candidates.map((c, i) => (
            <button
              key={c.id}
              type="button"
              disabled={submitting}
              onClick={() => pick(c.id)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "10px 12px",
                background: "transparent",
                border: 0,
                borderTop:
                  i === 0
                    ? "none"
                    : "1px solid var(--color-border-subtle)",
                fontSize: 13,
                fontFamily: "inherit",
                cursor: submitting ? "not-allowed" : "pointer",
                color: "var(--color-fg1)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--color-surface-3)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              <div>{c.label}</div>
              <div className="mono-xs" style={{ marginTop: 2 }}>
                {c.sub}
              </div>
            </button>
          ))}
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 14 }}>
        <button
          type="button"
          onClick={onClose}
          className="rl-btn rl-btn-ghost"
          disabled={submitting}
        >
          Close
        </button>
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Create-group dialog
// ---------------------------------------------------------------------------

function CreateGroupDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (g: GroupOut) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName("");
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("name required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const g = await createGroup(trimmed);
      await onCreated(g);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create group.");
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New group"
      description="Name it after the team or function — e.g. Finance, Eng Leads, Customer Success."
      maxWidth={400}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div style={{ marginBottom: 14 }}>
          <label
            style={{
              display: "block",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--color-fg2)",
              marginBottom: 6,
            }}
          >
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rl-input"
            placeholder="Finance"
            required
            autoFocus
            disabled={submitting}
            maxLength={64}
          />
          {error && (
            <div style={{ fontSize: 12, color: "var(--color-danger)", marginTop: 4 }}>
              {error}
            </div>
          )}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            type="button"
            onClick={onClose}
            className="rl-btn rl-btn-ghost"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rl-btn rl-btn-primary"
            disabled={submitting}
          >
            {submitting ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Layout helpers
// ---------------------------------------------------------------------------

function Section({
  title,
  count,
  icon,
  onAdd,
  addLabel,
  children,
}: {
  title: string;
  count: number;
  icon: React.ReactNode;
  onAdd: () => void;
  addLabel: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginTop: 18 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 10,
        }}
      >
        <span style={{ color: "var(--color-fg3)" }}>{icon}</span>
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--color-fg1)" }}>
          {title}
        </span>
        <span
          className="mono-xs"
          style={{
            background: "var(--color-surface-3)",
            padding: "1px 6px",
            borderRadius: 3,
          }}
        >
          {count}
        </span>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={onAdd}
          className="rl-btn rl-btn-ghost"
          style={{ padding: "4px 10px", fontSize: 12 }}
        >
          <UserPlus size={12} /> {addLabel}
        </button>
      </div>
      {children}
    </div>
  );
}

function Rows({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "var(--radius-sm)",
        overflow: "hidden",
      }}
    >
      {children}
    </div>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 12px",
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      {children}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div
      style={{
        padding: "12px 14px",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "var(--radius-sm)",
        fontSize: 13,
        color: "var(--color-fg3)",
      }}
    >
      {text}
    </div>
  );
}
