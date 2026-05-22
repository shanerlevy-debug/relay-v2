import { HeroSlackPreview } from "@/components/HeroSlackPreview";

/**
 * "In an incident" — sits between Features and Commands. Frames the
 * detailed Slack preview as what an actual ten-minute incident looks
 * like through Relay. The hero already shows setup-then-use briefly;
 * this is the slower take.
 */
export function InAction() {
  return (
    <section
      className="rl-section"
      style={{ background: "var(--color-surface-2)" }}
    >
      <div className="rl-section-inner rl-inaction-grid">
        <div>
          <div className="rl-eyebrow">In an incident</div>
          <h2 className="rl-h2" style={{ marginTop: 14, marginBottom: 20, maxWidth: 480 }}>
            Five minutes after you <em>wire it up.</em>
          </h2>
          <p
            style={{
              fontSize: 16,
              lineHeight: 1.6,
              color: "var(--color-fg3)",
              marginBottom: 20,
              maxWidth: 460,
            }}
          >
            Real thread, real `/relay` call, real audit row. The bot doesn&apos;t
            disappear into a private session — every reply lands where the
            team is already looking.
          </p>
          <ul
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              display: "flex",
              flexDirection: "column",
              gap: 10,
              fontSize: 13.5,
              color: "var(--color-fg2)",
            }}
          >
            <li>
              <span className="mono-xs" style={{ marginRight: 10 }}>01</span>
              Mention or slash-command in the channel.
            </li>
            <li>
              <span className="mono-xs" style={{ marginRight: 10 }}>02</span>
              Relay routes to the right agent by name; thread context follows.
            </li>
            <li>
              <span className="mono-xs" style={{ marginRight: 10 }}>03</span>
              Reply posts in-thread; one row in the audit log.
            </li>
          </ul>
        </div>

        <HeroSlackPreview />
      </div>
    </section>
  );
}
