import { RelayWordmark } from "@/components/RelayMark";

/**
 * Landing-page footer. Dark, lifted from mockup with Relay's link set.
 */
export function Footer() {
  const cols: Array<{ title: string; links: string[] }> = [
    { title: "Product", links: ["How it works", "Features", "Commands"] },
    { title: "Resources", links: ["Docs", "Quickstart", "Status"] },
    { title: "Company", links: ["Powerloom", "Privacy", "Contact"] },
  ];

  return (
    <footer
      style={{
        background: "rgb(var(--ink-950))",
        color: "rgb(var(--ink-100))",
        padding: "64px 32px 36px",
      }}
    >
      <div
        style={{
          maxWidth: "var(--content-max-w)",
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "1.5fr 1fr 1fr 1fr",
          gap: 48,
        }}
      >
        <div>
          <RelayWordmark size={32} inverse />
          <p
            style={{
              marginTop: 14,
              fontSize: 13,
              lineHeight: 1.6,
              color: "rgb(var(--ink-300))",
              maxWidth: 280,
            }}
          >
            The thin bridge between Slack and Claude managed agents.
          </p>
        </div>
        {cols.map((col) => (
          <div key={col.title}>
            <h5
              style={{
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: "rgb(var(--ink-300))",
                fontFamily: "var(--font-mono)",
                fontWeight: 500,
                margin: "0 0 14px",
              }}
            >
              {col.title}
            </h5>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {col.links.map((l) => (
                <li key={l} style={{ padding: "6px 0", fontSize: 13 }}>
                  <a href="#" style={{ color: "rgb(var(--ink-100))" }}>
                    {l}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div
        style={{
          maxWidth: "var(--content-max-w)",
          margin: "48px auto 0",
          paddingTop: 24,
          borderTop: "1px solid rgb(255 255 255 / 0.06)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "rgb(var(--ink-500))",
        }}
      >
        <span>© 2026 Relay · Built by the Powerloom team</span>
        <span>private beta</span>
      </div>
    </footer>
  );
}
