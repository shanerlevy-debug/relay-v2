"use client";

import { ChevronDown, ChevronRight, ScrollText } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { AuditListOut, AuditLogEntry, listAudit } from "@/lib/api";

/**
 * Audit timeline — paginated read-only view of the audit_log table.
 *
 * Rows are click-to-expand for full metadata_json inspection.
 * 'Load more' button appends the next page (no infinite scroll for v1).
 */
interface AuditTimelineProps {
  initial: AuditListOut;
  pageSize?: number;
}

const PAGE_SIZE = 50;

export function AuditTimeline({ initial, pageSize = PAGE_SIZE }: AuditTimelineProps) {
  const [entries, setEntries] = useState<AuditLogEntry[]>(initial.entries);
  const [hasMore, setHasMore] = useState(initial.has_more);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  async function loadMore() {
    setLoading(true);
    setError(null);
    try {
      const next = await listAudit(pageSize, entries.length);
      setEntries((prev) => [...prev, ...next.entries]);
      setHasMore(next.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load more.");
    }
    setLoading(false);
  }

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  if (entries.length === 0) {
    return (
      <Card padding={48} style={{ textAlign: "center" }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: "50%",
            background: "var(--color-muted-tint)",
            color: "var(--color-fg2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 16px",
          }}
        >
          <ScrollText size={22} />
        </div>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>No activity yet</h2>
        <p
          style={{
            margin: "6px auto 0",
            fontSize: 13,
            color: "var(--color-fg3)",
            maxWidth: 360,
          }}
        >
          Every admin action and every routed Slack message lands here. Add an agent or
          connect Slack to start the log.
        </p>
      </Card>
    );
  }

  return (
    <>
      <div
        style={{
          background: "var(--color-surface-2)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "160px 1fr 200px 28px",
            alignItems: "center",
            padding: "10px 16px",
            fontSize: 11,
            fontFamily: "var(--font-mono)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--color-fg3)",
            background: "var(--color-surface-3)",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <div>When</div>
          <div>Event</div>
          <div>Actor</div>
          <div />
        </div>

        {entries.map((entry, idx) => (
          <AuditRow
            key={entry.id}
            entry={entry}
            first={idx === 0}
            expanded={expanded.has(entry.id)}
            onToggle={() => toggleExpand(entry.id)}
          />
        ))}
      </div>

      {error && (
        <div
          style={{
            padding: "10px 12px",
            background: "var(--color-danger-tint)",
            border: "1px solid var(--color-danger-border)",
            borderRadius: "var(--radius-sm)",
            color: "var(--color-danger)",
            fontSize: 13,
            marginTop: 12,
          }}
        >
          {error}
        </div>
      )}

      {hasMore && (
        <div style={{ marginTop: 16, textAlign: "center" }}>
          <button
            onClick={loadMore}
            className="rl-btn rl-btn-ghost"
            disabled={loading}
          >
            {loading ? "Loading…" : `Load ${pageSize} more`}
          </button>
        </div>
      )}

      {!hasMore && entries.length > pageSize && (
        <p
          style={{
            marginTop: 16,
            textAlign: "center",
            fontSize: 12,
            color: "var(--color-fg4)",
            fontFamily: "var(--font-mono)",
          }}
        >
          end of log
        </p>
      )}
    </>
  );
}

function AuditRow({
  entry,
  first,
  expanded,
  onToggle,
}: {
  entry: AuditLogEntry;
  first: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const hasDetail = Object.keys(entry.metadata_json).length > 0;
  return (
    <>
      <div
        onClick={hasDetail ? onToggle : undefined}
        style={{
          display: "grid",
          gridTemplateColumns: "160px 1fr 200px 28px",
          alignItems: "center",
          padding: "12px 16px",
          fontSize: 13,
          borderTop: first ? "none" : "1px solid var(--color-border-subtle)",
          cursor: hasDetail ? "pointer" : "default",
          transition: "background 120ms",
        }}
        onMouseEnter={(e) => {
          if (hasDetail) e.currentTarget.style.background = "var(--color-surface-3)";
        }}
        onMouseLeave={(e) => {
          if (hasDetail) e.currentTarget.style.background = "transparent";
        }}
      >
        <div className="mono-xs" style={{ color: "var(--color-fg2)", fontSize: 12 }}>
          {formatRelative(entry.occurred_at)}
        </div>
        <div>
          <div className="mono" style={{ fontSize: 13, color: "var(--color-fg1)" }}>
            {entry.event_type}
          </div>
          {(() => {
            const summary = summarize(entry);
            return summary ? (
              <div
                style={{
                  fontSize: 12,
                  color: "var(--color-fg3)",
                  marginTop: 2,
                  lineHeight: 1.4,
                }}
              >
                {summary}
              </div>
            ) : null;
          })()}
        </div>
        <div
          className="mono-xs"
          style={{
            color: entry.actor_email ? "var(--color-fg2)" : "var(--color-fg4)",
            fontStyle: entry.actor_email ? "normal" : "italic",
          }}
        >
          {entry.actor_email ?? "(system)"}
        </div>
        <div style={{ color: "var(--color-fg3)", display: "flex", justifyContent: "center" }}>
          {hasDetail ? (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : null}
        </div>
      </div>

      {expanded && hasDetail && (
        <div
          style={{
            background: "var(--color-surface-3)",
            borderTop: "1px solid var(--color-border-subtle)",
            padding: "12px 24px",
          }}
        >
          <pre
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              margin: 0,
              color: "var(--color-fg2)",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              lineHeight: 1.5,
            }}
          >
            {JSON.stringify(entry.metadata_json, null, 2)}
          </pre>
        </div>
      )}
    </>
  );
}

/** Short human-readable summary for the row. Falls back to (none) for
 * events that have no metadata. */
function summarize(entry: AuditLogEntry): string | null {
  const m = entry.metadata_json;
  if (!m || Object.keys(m).length === 0) return null;
  switch (entry.event_type) {
    case "agent.created":
    case "agent.archived":
      return typeof m.slug === "string" ? `slug: ${m.slug}` : null;
    case "agent.updated":
      if (typeof m.slug !== "string") return null;
      if (m.changes && typeof m.changes === "object") {
        const keys = Object.keys(m.changes as Record<string, unknown>);
        return `${m.slug} · changed: ${keys.join(", ")}`;
      }
      return `slug: ${m.slug}`;
    case "agent.message_routed":
      const slug = typeof m.slug === "string" ? m.slug : "?";
      const reason = typeof m.reason === "string" ? m.reason : "?";
      return `${slug} · ${reason}`;
    case "user.invited":
    case "user.created_via_invite":
    case "user.removed":
      return typeof m.email === "string" ? `email: ${m.email}` : null;
    case "workspace.slack_installed":
      return typeof m.slack_team_name === "string" ? `team: ${m.slack_team_name}` : null;
    default:
      return null;
  }
}

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const diffMs = now - d.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 30) return "just now";
  if (diffMin < 1) return `${diffSec}s ago`;
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
