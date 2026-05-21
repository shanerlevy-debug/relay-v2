/**
 * Card — neutral container with border + radius. Used everywhere on
 * the console (Home cards, table containers, settings sections).
 */
import { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: number | string;
}

export function Card({ children, padding = 16, style, className, ...rest }: CardProps) {
  return (
    <div
      className={`rl-card ${className ?? ""}`}
      style={{ padding, ...style }}
      {...rest}
    >
      {children}
    </div>
  );
}
