/**
 * The lowercase "r" mark on a red square. Uses the original PNG variant
 * from the mockup (custom letterform with strong red bowl).
 */
import Image from "next/image";

interface RelayMarkProps {
  size?: number;
  className?: string;
}

export function RelayMark({ size = 36, className }: RelayMarkProps) {
  return (
    <Image
      src="/relay-mark.png"
      alt="Relay"
      width={size}
      height={size}
      priority
      className={className}
      style={{
        display: "block",
        borderRadius: Math.round(size * 0.14),
        flexShrink: 0,
      }}
    />
  );
}

interface RelayWordmarkProps {
  size?: number;
  inverse?: boolean;
  className?: string;
}

export function RelayWordmark({ size = 32, inverse = false, className }: RelayWordmarkProps) {
  return (
    <span
      className={className}
      style={{ display: "inline-flex", alignItems: "center", gap: 10 }}
    >
      <RelayMark size={size} />
      <span
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: size * 0.6,
          fontWeight: 600,
          letterSpacing: "-0.02em",
          color: inverse ? "rgb(var(--paper-50))" : "var(--color-fg1)",
          lineHeight: 1,
        }}
      >
        Relay
      </span>
    </span>
  );
}
