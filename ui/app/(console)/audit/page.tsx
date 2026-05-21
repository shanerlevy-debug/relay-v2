import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { listAuditServer } from "@/lib/api";

/**
 * Audit log page. Read-only event timeline for the current workspace.
 * Initial 50 rows fetched server-side; the client component handles
 * pagination from there.
 */
export default async function AuditPage() {
  const initial = await listAuditServer();

  return (
    <>
      <div style={{ marginBottom: 28 }}>
        <h1
          style={{
            margin: 0,
            fontSize: 24,
            fontWeight: 600,
            letterSpacing: "-0.015em",
          }}
        >
          Audit log
        </h1>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--color-fg3)" }}>
          Every admin action + every routed Slack message. Click a row to expand its
          metadata.
        </p>
      </div>

      <AuditTimeline initial={initial} />
    </>
  );
}
