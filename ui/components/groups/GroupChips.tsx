"use client";

import Link from "next/link";

import { GroupSummary } from "@/lib/api";

/**
 * Compact list of group memberships, rendered as small pills under an
 * agent or user row. Default group gets the accent tint; others are
 * neutral. Hard-cap at 4 visible (shows "+N more" beyond that) to
 * keep row heights stable.
 */
export function GroupChips({
  groups,
  max = 4,
}: {
  groups: GroupSummary[];
  max?: number;
}) {
  if (!groups || groups.length === 0) return null;
  const visible = groups.slice(0, max);
  const overflow = groups.length - visible.length;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 4,
        fontSize: 11,
        fontFamily: "var(--font-mono)",
      }}
    >
      <span
        style={{
          color: "var(--color-fg3)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginRight: 2,
        }}
      >
        Groups
      </span>
      {visible.map((g) => (
        <Chip key={g.id} group={g} />
      ))}
      {overflow > 0 && (
        <Link
          href="/groups"
          style={{
            padding: "1px 6px",
            borderRadius: 3,
            background: "var(--color-surface-3)",
            color: "var(--color-fg3)",
            textDecoration: "none",
          }}
        >
          +{overflow} more
        </Link>
      )}
    </span>
  );
}

function Chip({ group }: { group: GroupSummary }) {
  return (
    <Link
      href="/groups"
      title={group.is_default ? `${group.name} (default group)` : group.name}
      style={{
        padding: "1px 6px",
        borderRadius: 3,
        background: group.is_default
          ? "var(--color-accent-tint)"
          : "var(--color-surface-3)",
        color: group.is_default ? "var(--color-accent)" : "var(--color-fg2)",
        textDecoration: "none",
        fontWeight: 500,
        whiteSpace: "nowrap",
      }}
    >
      {group.name}
    </Link>
  );
}
