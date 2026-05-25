"use client";

/**
 * "Sign in with Slack" button — distinct from AddToSlackButton.
 *
 * AddToSlackButton installs the Relay bot in a Slack workspace
 * (admin action). This button authenticates a user against an
 * already-installed workspace via Slack's OIDC layer — the standard
 * "Sign in with Slack" pattern.
 *
 * Visual styling matches Slack's brand guidance: aubergine background,
 * white text, the 4-color Slack hash mark. We keep the existing
 * Google/Slack-install buttons' shape so the three CTAs feel like
 * siblings on /login + /signup.
 */

export function SlackSignInButton({
  label = "Sign in with Slack",
  variant = "default",
}: {
  label?: string;
  variant?: "default" | "dark";
}) {
  const styles = variant === "dark" ? DARK : LIGHT;
  return (
    <a
      href="/api/oauth/slack-signin/start"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        width: "100%",
        padding: "10px 14px",
        background: styles.bg,
        color: styles.fg,
        border: styles.border,
        borderRadius: "var(--radius-sm)",
        fontSize: 13,
        fontWeight: 500,
        textDecoration: "none",
        cursor: "pointer",
        transition: "background 120ms var(--ease-std), border-color 120ms var(--ease-std)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = styles.bgHover;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = styles.bg;
      }}
    >
      <SlackMark size={16} />
      {label}
    </a>
  );
}

const LIGHT = {
  bg: "#FFFFFF",
  bgHover: "#F8F7F3",
  fg: "#1F1F1F",
  border: "1px solid var(--color-border)",
};

const DARK = {
  bg: "#4A154B",
  bgHover: "#3B0E3C",
  fg: "#FFFFFF",
  border: "1px solid #4A154B",
};

function SlackMark({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 122.8 122.8"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M25.8,77.6c0,7.1-5.8,12.9-12.9,12.9S0,84.7,0,77.6s5.8-12.9,12.9-12.9h12.9V77.6z M32.3,77.6c0-7.1,5.8-12.9,12.9-12.9 s12.9,5.8,12.9,12.9v32.3c0,7.1-5.8,12.9-12.9,12.9s-12.9-5.8-12.9-12.9V77.6z"
        fill="#E01E5A"
      />
      <path
        d="M45.2,25.8c-7.1,0-12.9-5.8-12.9-12.9S38.1,0,45.2,0s12.9,5.8,12.9,12.9v12.9H45.2z M45.2,32.3c7.1,0,12.9,5.8,12.9,12.9 s-5.8,12.9-12.9,12.9H12.9C5.8,58.1,0,52.3,0,45.2s5.8-12.9,12.9-12.9H45.2z"
        fill="#36C5F0"
      />
      <path
        d="M97,45.2c0-7.1,5.8-12.9,12.9-12.9c7.1,0,12.9,5.8,12.9,12.9s-5.8,12.9-12.9,12.9H97V45.2z M90.5,45.2 c0,7.1-5.8,12.9-12.9,12.9c-7.1,0-12.9-5.8-12.9-12.9V12.9C64.7,5.8,70.5,0,77.6,0c7.1,0,12.9,5.8,12.9,12.9V45.2z"
        fill="#2EB67D"
      />
      <path
        d="M77.6,97c7.1,0,12.9,5.8,12.9,12.9c0,7.1-5.8,12.9-12.9,12.9c-7.1,0-12.9-5.8-12.9-12.9V97H77.6z M77.6,90.5 c-7.1,0-12.9-5.8-12.9-12.9c0-7.1,5.8-12.9,12.9-12.9h32.3c7.1,0,12.9,5.8,12.9,12.9c0,7.1-5.8,12.9-12.9,12.9H77.6z"
        fill="#ECB22E"
      />
    </svg>
  );
}
