import Link from "next/link";

import { Footer } from "@/components/landing/Footer";
import { RelayMark } from "@/components/RelayMark";

export const metadata = {
  title: "Pricing — relay",
  description:
    "Free up to 15 users. Pro at $19/mo. Scale at $50/mo. Enterprise via Powerloom.",
};

/**
 * /pricing — 4-card pricing page. Pop-up frame: low numbers, no tier above
 * $50/mo, Enterprise routes to Powerloom. See D:\Relay\RELAY-PRICING.md for
 * the strategic rationale + unit-economics math.
 */

export default function PricingPage() {
  return (
    <div>
      <PricingNav />
      <PricingHeader />
      <PricingGrid />
      <PricingFAQ />
      <Footer />
    </div>
  );
}

function PricingNav() {
  return (
    <header className="rl-topnav">
      <div className="rl-topnav-inner">
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <RelayMark size={28} />
          <span
            style={{
              fontSize: 17,
              fontWeight: 600,
              letterSpacing: "-0.01em",
              color: "rgb(var(--paper-50))",
            }}
          >
            relay
          </span>
        </Link>
        <div style={{ flex: 1 }} />
        <nav className="rl-topnav-links" style={{ display: "flex", gap: 24, fontSize: 13 }}>
          <Link href="/#how" className="rl-topnav-link">
            How it works
          </Link>
          <Link href="/#features" className="rl-topnav-link">
            Features
          </Link>
          <Link href="/pricing" className="rl-topnav-link" style={{ color: "rgb(var(--paper-50))" }}>
            Pricing
          </Link>
        </nav>
        <span
          className="rl-topnav-divider"
          style={{ width: 1, height: 18, background: "rgb(255 255 255 / 0.1)" }}
        />
        <Link
          href="/login"
          className="rl-btn rl-topnav-signin"
          style={{
            background: "transparent",
            color: "rgb(var(--paper-50))",
            border: "1px solid rgb(255 255 255 / 0.18)",
          }}
        >
          Sign in
        </Link>
        <Link href="/signup" className="rl-btn rl-btn-primary">
          Create workspace →
        </Link>
      </div>
    </header>
  );
}

function PricingHeader() {
  return (
    <section className="rl-hero" style={{ paddingBottom: 0 }}>
      <div
        style={{
          maxWidth: 880,
          margin: "0 auto",
          padding: "80px 32px 48px",
          textAlign: "center",
        }}
      >
        <div
          className="rl-eyebrow"
          style={{
            color: "rgb(var(--relay-300))",
            marginBottom: 18,
          }}
        >
          Pricing
        </div>
        <h1
          className="rl-display-xl"
          style={{
            color: "rgb(var(--paper-50))",
            margin: 0,
            marginBottom: 24,
          }}
        >
          Cheap enough to <em>expense.</em>
        </h1>
        <p
          style={{
            fontSize: 18,
            lineHeight: 1.55,
            color: "rgb(var(--ink-100))",
            maxWidth: 620,
            margin: "0 auto",
          }}
        >
          Bring your own Anthropic key. We charge for the convenience of the
          pipe, not for your token spend. No tier above $50/mo —
          if you outgrow Scale, you outgrow Relay.
        </p>
      </div>
    </section>
  );
}

function PricingGrid() {
  return (
    <section
      style={{
        background: "var(--color-surface)",
        padding: "48px 32px 80px",
      }}
    >
      <div
        className="rl-pricing-grid"
        style={{
          maxWidth: "var(--content-max-w)",
          margin: "0 auto",
        }}
      >
        <Tier
          name="Free"
          price="$0"
          cadence="forever"
          tagline="The pop-up's free table."
          features={[
            "Up to 15 users",
            "Up to 15 agents",
            "Unlimited Slack messages",
            "BYO Anthropic key",
            "Slack-native install",
            "Audit log built in",
          ]}
          cta={{ label: "Get started", href: "/signup" }}
        />

        <Tier
          name="Pro"
          price="$19"
          cadence="per month"
          tagline="For growing teams."
          features={[
            "Up to 150 users",
            "Unlimited agents",
            "Everything in Free",
            "Priority email support",
          ]}
          cta={{ label: "Start Pro", href: "/signup?plan=pro" }}
          recommended
        />

        <Tier
          name="Scale"
          price="$50"
          cadence="per month"
          tagline="Departments, not just teams."
          features={[
            "Up to 500 users",
            "Unlimited agents",
            "Everything in Pro",
            "Faster response SLA",
          ]}
          cta={{ label: "Start Scale", href: "/signup?plan=scale" }}
        />

        <Tier
          name="Enterprise"
          price="Custom"
          cadence="via Powerloom"
          tagline="When you outgrow the pop-up."
          features={[
            "Multi-workspace",
            "SSO / SAML",
            "RBAC + per-channel permissions",
            "SOC 2 + DPAs",
            "Custom retention + audit export",
            "Dedicated support + SLA",
          ]}
          cta={{ label: "Talk to us", href: "mailto:hello@powerloom.dev?subject=Relay%20Enterprise" }}
          enterprise
        />
      </div>
    </section>
  );
}

interface TierProps {
  name: string;
  price: string;
  cadence: string;
  tagline: string;
  features: string[];
  cta: { label: string; href: string };
  recommended?: boolean;
  enterprise?: boolean;
}

function Tier({
  name,
  price,
  cadence,
  tagline,
  features,
  cta,
  recommended,
  enterprise,
}: TierProps) {
  return (
    <div
      className="rl-pricing-card"
      data-recommended={recommended ? "true" : "false"}
      data-enterprise={enterprise ? "true" : "false"}
    >
      {recommended && (
        <div className="rl-pricing-card-badge">Most popular</div>
      )}

      <div style={{ marginBottom: 12 }}>
        <div
          style={{
            fontSize: 13,
            fontFamily: "var(--font-mono)",
            color: "var(--color-fg3)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: 6,
          }}
        >
          {name}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span
            style={{
              fontSize: 36,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              color: "var(--color-fg1)",
            }}
          >
            {price}
          </span>
          <span style={{ fontSize: 13, color: "var(--color-fg3)" }}>
            {cadence}
          </span>
        </div>
        <div
          style={{
            fontSize: 13,
            color: "var(--color-fg3)",
            marginTop: 8,
            lineHeight: 1.4,
          }}
        >
          {tagline}
        </div>
      </div>

      <hr
        style={{
          border: 0,
          borderTop: "1px solid var(--color-border-subtle)",
          margin: "16px 0",
        }}
      />

      <ul
        style={{
          listStyle: "none",
          padding: 0,
          margin: 0,
          marginBottom: 24,
          minHeight: 168,
        }}
      >
        {features.map((f) => (
          <li
            key={f}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: "5px 0",
              fontSize: 13.5,
              lineHeight: 1.45,
              color: "var(--color-fg2)",
            }}
          >
            <Check />
            <span>{f}</span>
          </li>
        ))}
      </ul>

      <Link
        href={cta.href}
        className={
          recommended
            ? "rl-btn rl-btn-primary"
            : enterprise
              ? "rl-btn"
              : "rl-btn"
        }
        style={{
          width: "100%",
          justifyContent: "center",
          ...(enterprise
            ? {
                background: "var(--color-surface-2)",
                color: "var(--color-fg1)",
                border: "1px solid var(--color-border)",
              }
            : recommended
              ? {}
              : {
                  background: "var(--color-surface-2)",
                  color: "var(--color-fg1)",
                  border: "1px solid var(--color-border)",
                }),
        }}
      >
        {cta.label}
      </Link>
    </div>
  );
}

function Check() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      style={{ flexShrink: 0, marginTop: 3 }}
      aria-hidden="true"
    >
      <path
        d="M3 8.5L6.5 12L13 5"
        stroke="var(--color-accent)"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PricingFAQ() {
  const faqs = [
    {
      q: "What's BYOK — and why?",
      a: "Bring Your Own Key. You paste your Anthropic API key into Settings; Relay encrypts it and uses it to talk to Claude on your behalf. Your token spend goes on your Anthropic bill, not ours. That's why our prices are so much lower than the per-user pricing you'd see on most AI SaaS.",
    },
    {
      q: "What happens if I exceed my user cap?",
      a: "We don't auto-charge or auto-upgrade. New users beyond the cap can't be invited until you bump the tier from Settings or remove an existing user. Existing users keep working.",
    },
    {
      q: "Can I change tiers later?",
      a: "Upgrade is immediate and pro-rated. Downgrade kicks in at the end of the current billing cycle. No fees either way.",
    },
    {
      q: "Why no tier above $50/mo?",
      a: "Because that's where Relay ends. If you need multi-workspace, SSO, RBAC, SOC 2 attestation, or any other enterprise-shaped feature, you've outgrown the pop-up. Powerloom is the upgrade path — same team, same trust model, much richer surface.",
    },
    {
      q: "Refund policy?",
      a: "Pro-rated refund on request within 30 days. After that, no refunds, but you can downgrade or cancel at any time.",
    },
  ];

  return (
    <section
      style={{
        background: "var(--color-surface)",
        padding: "16px 32px 96px",
      }}
    >
      <div
        style={{
          maxWidth: 720,
          margin: "0 auto",
        }}
      >
        <h2
          className="rl-h2"
          style={{ marginBottom: 32, textAlign: "center", fontSize: 32 }}
        >
          Questions.
        </h2>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 0,
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            background: "var(--color-surface-2)",
          }}
        >
          {faqs.map((f, i) => (
            <div
              key={f.q}
              style={{
                padding: "20px 24px",
                borderTop: i === 0 ? "none" : "1px solid var(--color-border-subtle)",
              }}
            >
              <div
                style={{
                  fontWeight: 500,
                  fontSize: 15,
                  color: "var(--color-fg1)",
                  marginBottom: 6,
                  letterSpacing: "-0.005em",
                }}
              >
                {f.q}
              </div>
              <div
                style={{
                  fontSize: 14,
                  lineHeight: 1.55,
                  color: "var(--color-fg2)",
                }}
              >
                {f.a}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
