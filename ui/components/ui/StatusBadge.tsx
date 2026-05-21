/**
 * StatusBadge — colored pill with a dot, used to communicate state
 * (connected, running, pending, failed, etc.). Pulses when `pulse=true`
 * to indicate an in-flight operation.
 */

export type BadgeStatus =
  | "healthy"
  | "connected"
  | "running"
  | "idle"
  | "pending"
  | "warning"
  | "failed"
  | "terminated"
  | "muted";

interface StatusBadgeProps {
  status: BadgeStatus;
  label?: string;
  pulse?: boolean;
}

const tone: Record<BadgeStatus, "success" | "accent" | "warning" | "danger" | "muted"> = {
  healthy: "success",
  connected: "success",
  running: "accent",
  idle: "muted",
  pending: "warning",
  warning: "warning",
  failed: "danger",
  terminated: "muted",
  muted: "muted",
};

export function StatusBadge({ status, label, pulse }: StatusBadgeProps) {
  return (
    <span className={`rl-badge rl-badge-${tone[status]}`}>
      <span className={`rl-dot ${pulse ? "rl-pulse" : ""}`} />
      {label ?? status}
    </span>
  );
}
