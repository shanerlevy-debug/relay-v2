import { Footer } from "@/components/landing/Footer";
import {
  Bullets,
  DocNav,
  Email,
  H2,
  Mono,
  P,
} from "@/app/privacy/page";

export const metadata = {
  title: "Terms of Service — relay",
  description:
    "Terms of Service for relayed.live — usage, billing, liability, and the not-fun parts you read once.",
};

const LAST_UPDATED = "May 22, 2026";

/**
 * /terms — Standard SaaS Terms of Service.
 *
 * Bespoke Technology Solutions is the contracting party. Generic
 * but defensible boilerplate suitable for OAuth provider intake
 * (Google, Slack) and small-team commercial use.
 */

export default function TermsPage() {
  return (
    <div>
      <DocNav active="terms" />
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
            Terms of Service
          </div>
          <h1
            className="rl-h2"
            style={{ margin: 0, marginBottom: 8, fontSize: 36 }}
          >
            The agreement, in plain enough language.
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
          These Terms of Service (&quot;Terms&quot;) govern your access to
          and use of the Relay service (the &quot;Service&quot;) at{" "}
          <Mono>relayed.live</Mono>, operated by Bespoke Technology
          Solutions (&quot;Bespoke&quot;, &quot;we&quot;, or
          &quot;us&quot;). By creating an account or using the Service, you
          agree to be bound by these Terms. If you do not agree, do not
          use the Service.
        </P>

        <H2>1. Eligibility &amp; Account</H2>
        <P>
          You must be at least 13 years old to use the Service. If you are
          using the Service on behalf of an organization, you represent
          that you have authority to bind that organization to these
          Terms. You are responsible for safeguarding your account
          credentials and for all activity that occurs under your account.
        </P>

        <H2>2. The Service</H2>
        <P>
          Relay is a multi-tenant bridge between Slack and the Anthropic
          Managed Agents service. You bring your own Anthropic API key,
          install Relay into your Slack workspace, and configure agents
          that respond to messages in Slack. We provide the routing
          layer; you provide the credentials and the workspace.
        </P>

        <H2>3. Your Responsibilities</H2>
        <Bullets>
          <li>
            <strong>Lawful use.</strong> You will use the Service only in
            compliance with applicable law and with these Terms, the
            Slack API Terms of Service, and Anthropic&apos;s Usage Policy
            and Service Terms.
          </li>
          <li>
            <strong>Content.</strong> You are responsible for the
            messages users in your Slack workspace send through the
            Service, for the prompts you provide to agents, and for the
            outputs those agents produce. You will not use the Service
            to generate content that is unlawful, harmful, or that
            infringes the rights of others.
          </li>
          <li>
            <strong>Credentials.</strong> You will keep your Anthropic
            API key, Slack credentials, and Relay account credentials
            confidential. You will notify us promptly of any
            unauthorized use.
          </li>
          <li>
            <strong>Acceptable use.</strong> You will not (i) attempt to
            reverse-engineer, decompile, or extract source code from the
            Service except as permitted by law; (ii) interfere with the
            Service&apos;s operation; (iii) use the Service to
            send spam or unsolicited communications; (iv) circumvent
            usage limits or access controls; or (v) use the Service in
            any manner that could disable, overburden, or impair its
            availability for other users.
          </li>
        </Bullets>

        <H2>4. Bring-Your-Own-Key (BYOK)</H2>
        <P>
          The Service requires you to provide your own Anthropic API key.
          You are solely responsible for usage and charges incurred on
          that key. We do not control, audit, or guarantee Anthropic&apos;s
          billing. We are not liable for charges, throttling, suspensions,
          or other actions Anthropic takes with respect to your account.
        </P>

        <H2>5. Plans &amp; Billing</H2>
        <Bullets>
          <li>
            <strong>Plans.</strong> Plan tiers and prices are published at
            relayed.live/pricing. We may change pricing on 30 days&apos;
            notice; existing paid subscriptions are honored at their
            current price until the end of the then-current billing
            period.
          </li>
          <li>
            <strong>Payments.</strong> Paid plans are billed in advance,
            monthly, via Stripe. By subscribing you authorize us to
            charge your designated payment method.
          </li>
          <li>
            <strong>Failed payments.</strong> If payment fails, we will
            retry the charge and email the administrator. If payment
            remains unrecoverable, we will downgrade your workspace to
            the Free tier. Your data remains intact; usage exceeding the
            Free tier&apos;s caps is throttled until you resolve billing.
          </li>
          <li>
            <strong>Refunds.</strong> We offer pro-rated refunds on
            request within 30 days of charge. After 30 days, all fees are
            non-refundable. You can cancel or downgrade at any time;
            changes take effect at the end of the current billing period.
          </li>
          <li>
            <strong>Taxes.</strong> Prices exclude applicable taxes.
            Where required, taxes will be added at checkout.
          </li>
        </Bullets>

        <H2>6. Intellectual Property</H2>
        <P>
          The Service, including its software, design, branding, and
          documentation, is owned by Bespoke and is protected by
          applicable intellectual property laws. You retain all rights
          to the content you provide to the Service (prompts, agent
          configurations, output displayed in your Slack workspace).
          You grant us a limited license to host, process, and transmit
          that content solely as needed to operate the Service for you.
        </P>

        <H2>7. Feedback</H2>
        <P>
          If you provide suggestions, feature requests, or other feedback
          to us, we may use it without restriction or compensation. You
          retain no rights in the feedback once provided.
        </P>

        <H2>8. Confidentiality</H2>
        <P>
          To the extent you share confidential information with us, we
          will use commercially reasonable efforts to protect it with at
          least the same care we use for our own confidential
          information. We do not access the content of your Slack
          messages except as needed to operate the Service.
        </P>

        <H2>9. Termination</H2>
        <P>
          You may terminate your account at any time by deleting your
          workspace from Settings. We may suspend or terminate access
          immediately if (i) you breach these Terms, (ii) the Service is
          required by law to be discontinued, (iii) we discontinue the
          Service entirely with 30 days&apos; advance notice, or (iv) your
          account is inactive for more than 12 months. Sections 6, 10,
          11, and 12 survive termination.
        </P>

        <H2>10. Warranties &amp; Disclaimers</H2>
        <P>
          THE SERVICE IS PROVIDED &quot;AS IS&quot; AND &quot;AS
          AVAILABLE&quot;. TO THE FULLEST EXTENT PERMITTED BY LAW, WE
          DISCLAIM ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING
          MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND
          NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE
          UNINTERRUPTED, ERROR-FREE, OR SECURE; THAT MESSAGES WILL BE
          ROUTED WITHOUT DELAY; OR THAT AGENT OUTPUTS WILL BE ACCURATE,
          RELIABLE, OR APPROPRIATE FOR YOUR USE CASE.
        </P>

        <H2>11. Limitation of Liability</H2>
        <P>
          TO THE FULLEST EXTENT PERMITTED BY LAW, IN NO EVENT WILL BESPOKE
          OR ITS AFFILIATES BE LIABLE FOR ANY INDIRECT, INCIDENTAL,
          SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR ANY
          LOSS OF PROFITS, DATA, OR GOODWILL, ARISING OUT OF OR RELATING
          TO YOUR USE OF THE SERVICE, EVEN IF ADVISED OF THE POSSIBILITY.
          OUR AGGREGATE LIABILITY ARISING OUT OF OR RELATING TO THESE
          TERMS OR THE SERVICE WILL NOT EXCEED THE GREATER OF (A) THE
          FEES YOU PAID US IN THE 12 MONTHS BEFORE THE EVENT GIVING RISE
          TO LIABILITY OR (B) USD $100. THE FOREGOING DOES NOT LIMIT
          LIABILITY THAT CANNOT BE LIMITED UNDER APPLICABLE LAW.
        </P>

        <H2>12. Indemnification</H2>
        <P>
          You will defend, indemnify, and hold harmless Bespoke and its
          officers, directors, employees, and affiliates from any third-
          party claims, damages, liabilities, and expenses (including
          reasonable attorneys&apos; fees) arising out of (i) your use of
          the Service in violation of these Terms or applicable law,
          (ii) your content, prompts, or agent outputs, or (iii) your
          violation of any third party&apos;s rights.
        </P>

        <H2>13. Governing Law &amp; Disputes</H2>
        <P>
          These Terms are governed by the laws of the State of Delaware,
          United States, without regard to its conflict-of-laws
          principles. The exclusive venue for any dispute arising under
          these Terms is the state or federal courts located in
          Wilmington, Delaware, and the parties consent to personal
          jurisdiction in those courts.
        </P>

        <H2>14. Changes</H2>
        <P>
          We may modify these Terms from time to time. Material changes
          will be posted on this page and communicated by email to
          workspace administrators at least 14 days before they take
          effect. Continued use of the Service after the effective date
          constitutes acceptance.
        </P>

        <H2>15. General</H2>
        <P>
          These Terms, together with the Privacy Policy, constitute the
          entire agreement between you and Bespoke regarding the Service
          and supersede all prior or contemporaneous understandings. If
          any provision is found to be unenforceable, the remaining
          provisions remain in full force. Our failure to enforce a
          provision is not a waiver. You may not assign these Terms
          without our consent; we may assign them in connection with a
          merger, acquisition, or sale of substantially all our assets.
        </P>

        <H2>16. Contact</H2>
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
