/**
 * Commands section — Slack-native invocation surface.
 *
 * The mockup had three code tabs (slack/curl/relay.yml). For pop-up scope
 * we ship only the Slack tab — the API and YAML versions imply a public
 * API + config-file workflow we don't have in v1.
 */
export function Commands() {
  const rows: Array<[string, string]> = [
    ["Mention", "@relay summarize this thread"],
    ["Slash command", '/relay vanguard "what\'s happening in semis"'],
    ["Untagged default", "Hit @relay with no slug — the workspace's default agent answers"],
    ["DM", "Send @relay a DM for a private session"],
  ];

  return (
    <section id="commands" className="rl-section" style={{ background: "var(--color-surface)" }}>
      <div className="rl-section-inner">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1.2fr",
            gap: 56,
            alignItems: "center",
          }}
        >
          <div>
            <div className="rl-eyebrow">Commands</div>
            <h2 className="rl-h2" style={{ marginTop: 14, marginBottom: 20, fontSize: 40 }}>
              Slack is the <em>terminal.</em>
            </h2>
            <p
              style={{
                fontSize: 16,
                lineHeight: 1.6,
                color: "var(--color-fg3)",
                marginBottom: 24,
              }}
            >
              Four ways to invoke. Pick the one that fits your team&apos;s muscle memory.
            </p>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {rows.map(([k, v]) => (
                <li
                  key={k}
                  style={{
                    padding: "12px 0",
                    borderTop: "1px solid var(--color-border-subtle)",
                    display: "grid",
                    gridTemplateColumns: "150px 1fr",
                    gap: 16,
                    alignItems: "baseline",
                  }}
                >
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{k}</span>
                  <span className="mono-sm" style={{ color: "var(--color-fg2)" }}>
                    {v}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* Code sample — dark, Slack-flavored */}
          <div
            style={{
              background: "rgb(var(--ink-950))",
              color: "rgb(var(--paper-50))",
              borderRadius: 8,
              border: "1px solid rgb(255 255 255 / 0.08)",
              overflow: "hidden",
              fontFamily: "var(--font-mono)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 14px",
                borderBottom: "1px solid rgb(255 255 255 / 0.06)",
                fontSize: 11,
                color: "rgb(var(--ink-300))",
              }}
            >
              <span
                style={{
                  background: "rgb(255 255 255 / 0.06)",
                  color: "rgb(var(--paper-50))",
                  padding: "4px 10px",
                  borderRadius: 4,
                }}
              >
                slack message
              </span>
              <div style={{ flex: 1 }} />
              <span style={{ color: "rgb(var(--ink-500))" }}>copy</span>
            </div>
            <pre
              style={{
                margin: 0,
                padding: "18px 22px",
                fontSize: 12.5,
                lineHeight: 1.75,
                whiteSpace: "pre",
                overflowX: "auto",
              }}
            >
              <span style={{ color: "rgb(var(--ink-300))" }}># in #prod-incidents</span>
              {"\n"}
              <span style={{ color: "rgb(var(--ink-300))" }}>
                # anyone in the workspace can do this
              </span>
              {"\n\n"}
              <span style={{ color: "rgb(var(--relay-300))" }}>/relay</span>{" "}
              <span style={{ color: "rgb(var(--paper-50))" }}>runbook</span>{" "}
              <span style={{ color: "#C8E6B4" }}>
                &quot;checkout-svc 5xx spike, started ~5m ago&quot;
              </span>
              {"\n\n"}
              <span style={{ color: "rgb(var(--ink-300))" }}># relay replies in the thread</span>
              {"\n"}
              <span style={{ color: "rgb(var(--ink-300))" }}>
                # follow-ups stay with the same agent
              </span>
              {"\n"}
              <span style={{ color: "rgb(var(--ink-300))" }}>
                # every routed message gets an audit row
              </span>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
