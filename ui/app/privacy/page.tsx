import Link from "next/link";

import { Footer } from "@/components/landing/Footer";
import { RelayMark } from "@/components/RelayMark";

export const metadata = {
  title: "Privacy Policy — relay",
  description:
    "How relay handles your data — what we collect, what we don't, how it's stored.",
};

const LAST_UPDATED = "May 22, 2026";

/**
 * /privacy — Standard SaaS privacy policy.
 *
 * Owned by Bespoke Technology Solutions (the legal entity behind
 * Relay + Powerloom). Generic but defensible for OAuth provider
 * intake (Google Cloud Console, Slack App Directory) where a
 * privacy policy is a required submission artifact.
 *
 * Update LAST_UPDATED when materially editing this page.
 */

export default function PrivacyPage() {
  return (
    <div>
      <DocNav active="privacy" />
      <article
        style={{
          maxWidth: 760,
          margin: "0 auto",
          padding: "64px 32px 80px",
          color: "var(--color-fg1)",
        }}
      >
        <header style={{ marginBottom: 32 }}>
          <div className="rl-eyebrow" style={{ marginBottom: 12 }}>
            Privacy Policy
          </div>
          <h1
            className="rl-h2"
            style={{ margin: 0, marginBottom: 8, fontSize: 36 }}
          >
            How we handle your data.
          </h1>
          <p
            style={{
              fontSize: 14,
              color: "var(--color-fg3)",
              margin: 0,
              fontFamily: "var(--font-mono)",
            }}
          >
            Last updated: {LAST_UPDATED}
          </p>
        </header>

        <P>
          This Privacy Policy describes how Bespoke Technology Solutions
          (&quot;we&quot;, &quot;us&quot;, or &quot;Relay&quot;) collects,
          uses, and discloses information when you use the Relay service
          accessible at <Mono>relayed.live</Mono> (the &quot;Service&quot;). By
          using the Service you agree to the collection and use of
          information in accordance with this policy.
        </P>

        <H2>1. Information We Collect</H2>
        <P>We collect the minimum information needed to operate the Service.</P>

        <H3>Information you provide</H3>
        <Bullets>
          <li>
            <strong>Account information.</strong> When you sign up, we
            collect your email address, workspace name, and (if
            authenticated with a password) a hashed version of that
            password. Passwords are stored as argon2id hashes; we cannot
            recover them.
          </li>
          <li>
            <strong>OAuth identifiers.</strong> If you sign in with Google
            or install the Service into a Slack workspace, we receive your
            email address, name, and the provider&apos;s stable user
            identifier. Slack installations additionally provide a bot
            token and the names of channels the bot is added to.
          </li>
          <li>
            <strong>Bring-your-own credentials.</strong> If you provide an
            Anthropic API key for use within your workspace, we encrypt and
            store it. We use the key solely to invoke the Anthropic
            Managed Agents service on your behalf when triggered from
            Slack.
          </li>
        </Bullets>

        <H3>Information collected automatically</H3>
        <Bullets>
          <li>
            <strong>Operational logs.</strong> We log request metadata
            (HTTP method, route, status, latency, request identifier) for
            debugging and abuse prevention. Logs are retained for up to 90
            days.
          </li>
          <li>
            <strong>Audit log.</strong> Material actions inside your
            workspace (agents created, members invited, Slack installs,
            messages routed) are recorded with timestamps and the actor
            identifier. The audit log is visible to workspace
            administrators.
          </li>
        </Bullets>

        <H3>Information we explicitly do not collect</H3>
        <Bullets>
          <li>
            We do not store the content of Slack messages. Messages are
            forwarded to Anthropic for processing under your Anthropic
            account and we do not retain message bodies or model
            responses beyond what appears in the Slack thread itself.
          </li>
          <li>
            We do not sell, rent, or trade your data with third parties
            for advertising or marketing purposes.
          </li>
          <li>
            We do not use your prompts, agent configurations, or model
            responses to train any model.
          </li>
        </Bullets>

        <H2>2. How We Use Information</H2>
        <Bullets>
          <li>To operate, maintain, and improve the Service.</li>
          <li>
            To route messages between Slack and your configured Anthropic
            agents.
          </li>
          <li>
            To send transactional emails (account, security, billing,
            invitations). We do not send marketing email.
          </li>
          <li>
            To investigate and prevent abuse, fraud, or violations of our
            Terms of Service.
          </li>
        </Bullets>

        <H2>3. Sharing &amp; Sub-processors</H2>
        <P>
          We rely on a small set of sub-processors to operate the Service.
          Each handles a specific function and only receives the data
          required for that function:
        </P>
        <Bullets>
          <li>
            <strong>Amazon Web Services (AWS).</strong> Hosting (EC2,
            EBS), DNS (Route 53). Data resides in the United States.
          </li>
          <li>
            <strong>Slack Technologies.</strong> Slack OAuth, event
            delivery, and Slack-side message storage. Slack handles your
            workspace&apos;s message content; we receive only event
            metadata.
          </li>
          <li>
            <strong>Anthropic.</strong> Model invocation under your
            bring-your-own API key. Anthropic&apos;s data handling is
            governed by Anthropic&apos;s own privacy policy and your
            agreement with Anthropic.
          </li>
          <li>
            <strong>Google LLC.</strong> Optional OAuth-based sign-in.
            Google receives only the OAuth handshake; we receive only
            your email, name, and Google user identifier.
          </li>
          <li>
            <strong>Stripe, Inc.</strong> Payment processing when you
            subscribe to a paid plan. Card data is handled directly by
            Stripe and never touches our systems.
          </li>
        </Bullets>

        <H2>4. Data Storage &amp; Security</H2>
        <P>
          Account data, audit logs, and operational metadata are stored on
          encrypted volumes in AWS US data centers. Sensitive credentials
          (Anthropic API keys, Slack bot tokens) are envelope-encrypted at
          rest with AES-256-GCM and bound to their row identifier with
          additional authenticated data so that ciphertexts cannot be
          swapped between tenants. All connections to the Service use TLS
          1.2 or higher.
        </P>
        <P>
          No system is perfectly secure. If we become aware of a breach
          materially affecting your data, we will notify the affected
          workspace administrators within 72 hours.
        </P>

        <H2>5. Data Retention</H2>
        <P>
          We retain account, workspace, and audit data for as long as your
          account is active. When you delete your workspace, we remove
          your data within 30 days, except where retention is required by
          law (for example, financial records for tax purposes).
          Operational logs are retained for up to 90 days.
        </P>

        <H2>6. Your Rights</H2>
        <Bullets>
          <li>
            You may export or delete your workspace data at any time by
            contacting <Email />. We respond to verified requests within
            30 days.
          </li>
          <li>
            You may disconnect the Slack integration from your Slack
            workspace administration panel; we will mark the install
            revoked and stop receiving events.
          </li>
          <li>
            You may remove your Anthropic API key from Settings &gt; BYOK at
            any time; we will delete the encrypted ciphertext immediately.
          </li>
          <li>
            Users in the European Economic Area, United Kingdom, or
            California have additional rights (access, rectification,
            erasure, portability, restriction, objection). To exercise
            these rights, contact <Email />.
          </li>
        </Bullets>

        <H2>7. International Transfers</H2>
        <P>
          The Service is hosted in the United States. If you access it
          from outside the United States, your data will be transferred
          to and processed in the United States. For users in the
          European Economic Area or United Kingdom, we rely on standard
          contractual clauses where applicable.
        </P>

        <H2>8. Children</H2>
        <P>
          The Service is not directed to children under 13 and we do not
          knowingly collect personal information from children under 13.
          If you believe we have collected data from a child under 13,
          contact <Email /> and we will delete it.
        </P>

        <H2>9. Changes to This Policy</H2>
        <P>
          We may update this policy from time to time. Material changes
          will be communicated by email to workspace administrators at
          least 14 days before they take effect. Continued use of the
          Service after the effective date constitutes acceptance of the
          updated policy.
        </P>

        <H2>10. Contact</H2>
        <P>
          For questions about this policy or to exercise your rights,
          contact:
        </P>
        <P>
          Bespoke Technology Solutions
          <br />
          <Email />
        </P>
      </article>
      <Footer />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared shell (nav + typographic helpers) — also reused by /terms.
// ---------------------------------------------------------------------------

export function DocNav({ active }: { active: "privacy" | "terms" }) {
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
          <Link
            href="/privacy"
            className="rl-topnav-link"
            style={{ color: active === "privacy" ? "rgb(var(--paper-50))" : undefined }}
          >
            Privacy
          </Link>
          <Link
            href="/terms"
            className="rl-topnav-link"
            style={{ color: active === "terms" ? "rgb(var(--paper-50))" : undefined }}
          >
            Terms
          </Link>
          <Link href="/pricing" className="rl-topnav-link">
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
      </div>
    </header>
  );
}

export function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2
      style={{
        fontSize: 20,
        fontWeight: 600,
        letterSpacing: "-0.015em",
        marginTop: 36,
        marginBottom: 12,
      }}
    >
      {children}
    </h2>
  );
}

export function H3({ children }: { children: React.ReactNode }) {
  return (
    <h3
      style={{
        fontSize: 15,
        fontWeight: 600,
        letterSpacing: "-0.005em",
        marginTop: 24,
        marginBottom: 8,
        color: "var(--color-fg1)",
      }}
    >
      {children}
    </h3>
  );
}

export function P({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontSize: 15,
        lineHeight: 1.65,
        margin: "0 0 16px",
        color: "var(--color-fg2)",
      }}
    >
      {children}
    </p>
  );
}

export function Bullets({ children }: { children: React.ReactNode }) {
  return (
    <ul
      style={{
        margin: "0 0 16px",
        padding: "0 0 0 20px",
        fontSize: 15,
        lineHeight: 1.65,
        color: "var(--color-fg2)",
      }}
    >
      {children}
    </ul>
  );
}

export function Mono({ children }: { children: React.ReactNode }) {
  return (
    <code
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 13,
        background: "var(--color-surface-2)",
        padding: "1px 5px",
        borderRadius: 3,
      }}
    >
      {children}
    </code>
  );
}

export function Email() {
  return (
    <a
      href="mailto:privacy@relayed.live"
      style={{ color: "var(--color-accent)" }}
    >
      privacy@relayed.live
    </a>
  );
}
