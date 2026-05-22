"use client";

/**
 * "Continue with Google" button — links to /api/oauth/google/start.
 *
 * Plain <a> so the browser does the redirect (the route 303s to
 * accounts.google.com). No client-side state, no JS needed beyond what
 * the page already loads.
 */

export function GoogleSignInButton({
  label = "Continue with Google",
}: {
  label?: string;
}) {
  return (
    <a
      href="/api/oauth/google/start"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        width: "100%",
        padding: "10px 14px",
        background: "#FFFFFF",
        color: "#1F1F1F",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-sm)",
        fontSize: 13,
        fontWeight: 500,
        textDecoration: "none",
        cursor: "pointer",
        transition: "background 120ms var(--ease-std), border-color 120ms var(--ease-std)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "#F8F7F3";
        e.currentTarget.style.borderColor = "var(--color-border-strong)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "#FFFFFF";
        e.currentTarget.style.borderColor = "var(--color-border)";
      }}
    >
      <GoogleLogo size={16} />
      {label}
    </a>
  );
}

/**
 * Inline 4-color Google "G" logo. Reference: Google's brand guidelines.
 * SVG only — no asset import needed.
 */
function GoogleLogo({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8c-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4C12.955 4 4 12.955 4 24s8.955 20 20 20s20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4C16.318 4 9.656 8.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  );
}
