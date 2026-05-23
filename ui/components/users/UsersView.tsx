"use client";

import { Plus, Trash2, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

import { LimitHitDialog } from "@/components/agents/LimitHitDialog";
import { GroupChips } from "@/components/groups/GroupChips";
import { InviteDialog } from "@/components/users/InviteDialog";
import { Card } from "@/components/ui/Card";
import {
  ApiError,
  deleteUser,
  getGroupMemberships,
  GroupMembershipMap,
  GroupSummary,
  InviteOut,
  listUsers,
  UserListItem,
  UserListOut,
} from "@/lib/api";

interface UsersViewProps {
  initial: UserListOut;
  currentUserId: string;
  isAdmin: boolean;
}

export function UsersView({ initial, currentUserId, isAdmin }: UsersViewProps) {
  const [data, setData] = useState<UserListOut>(initial);
  const [inviting, setInviting] = useState(false);
  const [limitHit, setLimitHit] = useState(false);
  const [topError, setTopError] = useState<string | null>(null);
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
        listUsers(),
        getGroupMemberships().catch(() => null),
      ]);
      setData(next);
      if (m) setMemberships(m);
    } catch (err) {
      setTopError(err instanceof Error ? err.message : "Failed to reload users.");
    }
  }

  function groupsForUser(userId: string): GroupSummary[] {
    return memberships?.users[userId] ?? [];
  }

  function openInvite() {
    if (data.seats.active + data.seats.pending_invites >= data.seats.cap) {
      setLimitHit(true);
      return;
    }
    setInviting(true);
  }

  async function onRemove(user: UserListItem) {
    if (user.id === currentUserId) {
      setTopError("You can't remove yourself. Log out instead.");
      return;
    }
    if (!confirm(`Remove ${user.email} from the workspace?`)) return;
    try {
      await deleteUser(user.id);
      await refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "last_admin") {
          setTopError(
            "Can't remove the last admin — promote another user first.",
          );
        } else {
          setTopError(err.message);
        }
      } else {
        setTopError("Failed to remove user.");
      }
    }
  }

  const totalSeats = data.seats.active + data.seats.pending_invites;
  const atCap = totalSeats >= data.seats.cap;

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
            Users
          </h1>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--color-fg3)" }}>
            Workspace members and pending invites. Admins manage agents, Slack install,
            and the Anthropic key.
          </p>
        </div>
        <div className="rl-page-header-actions">
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              color: atCap ? "var(--color-danger)" : "var(--color-fg3)",
            }}
          >
            {data.seats.active} of {data.seats.cap}
            {data.seats.pending_invites > 0 && (
              <span style={{ marginLeft: 8 }}>
                · {data.seats.pending_invites} pending
              </span>
            )}
          </span>
          {isAdmin && (
            <button onClick={openInvite} className="rl-btn rl-btn-primary">
              <UserPlus size={14} />
              Invite
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

      <ActiveUsersTable
        users={data.users}
        currentUserId={currentUserId}
        isAdmin={isAdmin}
        onRemove={onRemove}
        groupsFor={groupsForUser}
      />

      {data.pending_invites.length > 0 && (
        <>
          <h2
            style={{
              margin: "32px 0 12px",
              fontSize: 13,
              fontWeight: 500,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--color-fg3)",
              fontFamily: "var(--font-mono)",
            }}
          >
            Pending invites
          </h2>
          <PendingInvitesTable invites={data.pending_invites} />
        </>
      )}

      <InviteDialog
        open={inviting}
        onClose={() => setInviting(false)}
        onSent={refresh}
        onLimitHit={() => setLimitHit(true)}
      />

      <LimitHitDialog
        open={limitHit}
        onClose={() => setLimitHit(false)}
        context="user_limit"
        cap={data.seats.cap}
      />

      {isAdmin && data.users.length === 0 && data.pending_invites.length === 0 && (
        <Card padding={48} style={{ textAlign: "center", marginTop: 16 }}>
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
            <UserPlus size={22} />
          </div>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>No teammates yet</h2>
          <p
            style={{
              margin: "6px auto 16px",
              fontSize: 13,
              color: "var(--color-fg3)",
              maxWidth: 360,
            }}
          >
            Invite up to {data.seats.cap - 1} more people by email.
          </p>
          <button onClick={openInvite} className="rl-btn rl-btn-primary">
            <Plus size={14} />
            Send your first invite
          </button>
        </Card>
      )}
    </>
  );
}

function ActiveUsersTable({
  users,
  currentUserId,
  isAdmin,
  onRemove,
  groupsFor,
}: {
  users: UserListItem[];
  currentUserId: string;
  isAdmin: boolean;
  onRemove: (user: UserListItem) => void;
  groupsFor: (userId: string) => GroupSummary[];
}) {
  return (
    <div className="rl-table rl-table-stack-on-mobile">
      <div
        className="rl-table-head"
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 100px 130px 80px",
          alignItems: "center",
        }}
      >
        <div>Email</div>
        <div>Role</div>
        <div>Joined</div>
        <div />
      </div>

      {users.map((user) => {
        const isYou = user.id === currentUserId;
        return (
          <div
            key={user.id}
            className="rl-table-row"
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 100px 130px 80px",
              alignItems: "center",
            }}
          >
            <div>
              <div style={{ fontWeight: 500 }}>
                {user.email}
                {isYou && (
                  <span
                    style={{
                      marginLeft: 8,
                      fontSize: 10.5,
                      padding: "1px 6px",
                      borderRadius: 3,
                      background: "var(--color-accent-tint)",
                      color: "var(--color-accent)",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    you
                  </span>
                )}
              </div>
              {(() => {
                const gs = groupsFor(user.id);
                return gs.length > 0 ? (
                  <div style={{ marginTop: 4 }}>
                    <GroupChips groups={gs} />
                  </div>
                ) : null;
              })()}
            </div>
            <div className="mono-sm" style={{ color: "var(--color-fg2)" }}>
              {user.role}
            </div>
            <div className="mono-xs">{formatDate(user.created_at)}</div>
            <div style={{ textAlign: "right" }}>
              {isAdmin && !isYou && (
                <button
                  onClick={() => onRemove(user)}
                  className="rl-btn rl-btn-ghost"
                  style={{
                    padding: "5px 10px",
                    fontSize: 12,
                    color: "var(--color-fg3)",
                  }}
                  title="Remove user"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PendingInvitesTable({ invites }: { invites: InviteOut[] }) {
  return (
    <div className="rl-table rl-table-stack-on-mobile">
      <div
        className="rl-table-head"
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 100px 130px",
          alignItems: "center",
        }}
      >
        <div>Email</div>
        <div>Role</div>
        <div>Expires</div>
      </div>

      {invites.map((invite) => (
        <div
          key={invite.id}
          className="rl-table-row"
          style={{
            display: "grid",
            gridTemplateColumns: "2fr 100px 130px",
            alignItems: "center",
          }}
        >
          <div style={{ fontWeight: 500 }}>{invite.email}</div>
          <div className="mono-sm" style={{ color: "var(--color-fg2)" }}>
            {invite.role}
          </div>
          <div className="mono-xs">{formatExpiry(invite.expires_at)}</div>
        </div>
      ))}
    </div>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatExpiry(iso: string): string {
  const d = new Date(iso);
  const diffMs = d.getTime() - Date.now();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return "Expired";
  if (diffDays === 1) return "Tomorrow";
  return `In ${diffDays} days`;
}
