"use client";

import {
  Bot,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Settings,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode } from "react";

import { RelayMark } from "@/components/RelayMark";
import { logout, SessionOut } from "@/lib/api";

/**
 * Console layout — sidebar + main. Lifted from the mockup's chrome.jsx
 * Sidebar, adapted for pop-up scope (5 items: Home, Agents, Users,
 * Settings, Audit — no Workspaces, no Permissions, no Sessions).
 *
 * Hides admin-only nav items from non-admin users (Users + Settings).
 * Audit is read-only for everyone.
 */

const NAV: Array<{
  id: string;
  label: string;
  href: string;
  Icon: typeof LayoutDashboard;
  adminOnly?: boolean;
}> = [
  { id: "home", label: "Home", href: "/home", Icon: LayoutDashboard },
  { id: "agents", label: "Agents", href: "/agents", Icon: Bot },
  { id: "users", label: "Users", href: "/users", Icon: UsersRound, adminOnly: true },
  { id: "settings", label: "Settings", href: "/settings", Icon: Settings, adminOnly: true },
  { id: "audit", label: "Audit", href: "/audit", Icon: ScrollText },
];

export function AppShell({
  session,
  children,
}: {
  session: SessionOut;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const isAdmin = session.user.role === "admin";

  const visibleNav = NAV.filter((item) => !item.adminOnly || isAdmin);

  async function onLogout() {
    try {
      await logout();
    } catch {
      // Logout is fire-and-forget; even if the API call fails (e.g.
      // session already expired), we redirect to clear local state.
    }
    router.push("/login");
    router.refresh();
  }

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        background: "var(--color-surface)",
        color: "var(--color-fg1)",
      }}
    >
      <aside
        style={{
          width: "var(--sidebar-w)",
          flexShrink: 0,
          borderRight: "1px solid var(--color-border)",
          background: "var(--color-surface-2)",
          padding: "16px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 18,
          minHeight: "100vh",
          position: "sticky",
          top: 0,
        }}
      >
        {/* Brand */}
        <Link
          href="/home"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "4px 6px",
            borderRadius: 6,
          }}
        >
          <RelayMark size={30} />
          <div>
            <div
              style={{
                fontSize: 15,
                fontWeight: 600,
                letterSpacing: "-0.01em",
                color: "var(--color-fg1)",
              }}
            >
              Relay
            </div>
            <div
              style={{
                fontSize: 11,
                color: "var(--color-fg3)",
                marginTop: 1,
                fontFamily: "var(--font-mono)",
              }}
            >
              console
            </div>
          </div>
        </Link>

        {/* Workspace pill */}
        <div
          style={{
            padding: "8px 10px",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div
            style={{
              width: 22,
              height: 22,
              borderRadius: 4,
              background: "var(--color-accent)",
              color: "var(--color-accent-fg)",
              fontSize: 11,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              letterSpacing: 0,
              flexShrink: 0,
            }}
          >
            {(session.workspace.display_name[0] ?? "W").toUpperCase()}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: "var(--color-fg1)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {session.workspace.display_name}
            </div>
            <div className="mono-xs" style={{ fontSize: 10 }}>
              Free · {session.user.role}
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {visibleNav.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.id}
                href={item.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 10px",
                  borderRadius: "var(--radius-sm)",
                  textDecoration: "none",
                  borderLeft: `2px solid ${isActive ? "var(--color-accent)" : "transparent"}`,
                  paddingLeft: 10,
                  background: isActive ? "var(--color-accent-tint)" : "transparent",
                  color: isActive ? "var(--color-accent)" : "var(--color-fg1)",
                  fontSize: 13,
                  fontWeight: isActive ? 500 : 400,
                  transition: "background 120ms var(--ease-std), color 120ms var(--ease-std)",
                }}
              >
                <item.Icon size={15} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User card + logout */}
        <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 10px",
              borderRadius: "var(--radius-sm)",
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
            }}
          >
            <div
              style={{
                width: 26,
                height: 26,
                borderRadius: 4,
                background: "var(--color-surface-inv)",
                color: "var(--color-fg-inv)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11,
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {session.user.email[0]?.toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: "var(--color-fg1)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={session.user.email}
              >
                {session.user.email}
              </div>
              <div className="mono-xs" style={{ fontSize: 10 }}>
                {session.user.role}
              </div>
            </div>
          </div>

          <button onClick={onLogout} className="rl-shell-logout">
            <LogOut size={14} />
            Log out
          </button>
        </div>
      </aside>

      <main
        style={{
          flex: 1,
          minWidth: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            maxWidth: 1240,
            width: "100%",
            margin: "0 auto",
            padding: "28px 32px 64px",
            flex: 1,
          }}
        >
          {children}
        </div>
      </main>
    </div>
  );
}
