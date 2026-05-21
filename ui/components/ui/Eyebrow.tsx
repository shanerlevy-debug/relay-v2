import { ReactNode } from "react";

/**
 * Eyebrow — small uppercase label above a heading. Accent-colored by
 * default (the coral); pass `color` to override.
 */
export function Eyebrow({
  children,
  color,
  className,
  style,
}: {
  children: ReactNode;
  color?: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`rl-eyebrow ${className ?? ""}`}
      style={{ color: color ?? "var(--color-accent)", ...style }}
    >
      {children}
    </div>
  );
}
