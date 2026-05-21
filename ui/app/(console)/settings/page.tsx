import { AnthropicKeyPanel } from "@/components/settings/AnthropicKeyPanel";
import { PlanPanel } from "@/components/settings/PlanPanel";
import { SlackPanel } from "@/components/settings/SlackPanel";
import { getAnthropicKeyStatusServer, getMe } from "@/lib/api";

/**
 * Settings page. Server-fetches the BYOK status + session in parallel,
 * then renders three panels: Slack integration, Anthropic key, Plan.
 *
 * Workspace-name editing + Slack disconnect deferred to a polish pass —
 * neither is blocking first-customer onboarding.
 */
export default async function SettingsPage() {
  const [session, anthropicKey] = await Promise.all([
    getMe(),
    getAnthropicKeyStatusServer(),
  ]);
  const isAdmin = session.user.role === "admin";

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
          Settings
        </h1>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--color-fg3)" }}>
          Slack install, BYOK key, plan. Workspace-name editing lands with a polish pass.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <SlackPanel workspace={session.workspace} isAdmin={isAdmin} />
        <AnthropicKeyPanel initial={anthropicKey} isAdmin={isAdmin} />
        <PlanPanel />
      </div>
    </>
  );
}
