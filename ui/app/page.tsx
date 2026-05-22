import Link from "next/link";

import { AddToSlackButton } from "@/components/AddToSlackButton";
import { HeroFlow } from "@/components/HeroFlow";
import { CTA } from "@/components/landing/CTA";
import { Commands } from "@/components/landing/Commands";
import { Features } from "@/components/landing/Features";
import { Footer } from "@/components/landing/Footer";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { InAction } from "@/components/landing/InAction";
import { PowerloomCallout } from "@/components/landing/PowerloomCallout";
import { RelayMark } from "@/components/RelayMark";

/**
 * Landing page. Dark hero with the animated Slack preview, then light
 * sections (How it works, Features, Commands, Powerloom callout, CTA).
 *
 * For now: ships with just the Nav + Hero. The rest of the landing
 * sections lift in subsequent commits — they're static markup, no API.
 */

function LandingNav() {
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
            Relay
          </span>
        </Link>
        <span
          className="rl-topnav-tag"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10.5,
            padding: "3px 8px",
            border: "1px solid rgb(255 255 255 / 0.12)",
            borderRadius: 4,
            color: "rgb(var(--ink-100))",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          Slack ↔ Claude
        </span>
        <div style={{ flex: 1 }} />
        <nav className="rl-topnav-links" style={{ display: "flex", gap: 24, fontSize: 13 }}>
          <a href="#how" className="rl-topnav-link">
            How it works
          </a>
          <a href="#features" className="rl-topnav-link">
            Features
          </a>
          <a href="#commands" className="rl-topnav-link">
            Commands
          </a>
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

function Hero() {
  return (
    <section className="rl-hero">
      <div
        className="rl-hero-inner"
        style={{
          maxWidth: "var(--content-max-w)",
          margin: "0 auto",
          padding: "80px 32px 96px",
          position: "relative",
        }}
      >
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "5px 12px",
              border: "1px solid rgb(var(--relay-300) / 0.35)",
              borderRadius: 20,
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "rgb(var(--relay-300))",
              textTransform: "uppercase",
              letterSpacing: "0.12em",
              marginBottom: 28,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "rgb(var(--relay-300))",
                boxShadow: "0 0 10px rgb(var(--relay-300))",
              }}
            />
            From the Powerloom team · private beta
          </div>

          <h1 className="rl-display-xl" style={{ color: "rgb(var(--paper-50))", maxWidth: 720 }}>
            Your Claude agents, <em>one mention away.</em>
          </h1>

          <p
            style={{
              fontSize: 20,
              lineHeight: 1.5,
              color: "rgb(var(--ink-100))",
              maxWidth: 560,
              margin: "28px 0 36px",
            }}
          >
            Mention{" "}
            <span className="mono" style={{ color: "rgb(var(--relay-300))" }}>
              @relay
            </span>{" "}
            in any channel — answers land in the thread. The thin bridge between
            Slack and Claude managed agents. Bring your own Anthropic key.
          </p>

          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 16 }}>
            <AddToSlackButton variant="dark" size="lg" />
            <Link href="/signup" className="rl-btn rl-btn-primary rl-btn-lg">
              Start free in 2 minutes
            </Link>
            <Link
              href="/login"
              className="rl-btn"
              style={{
                background: "transparent",
                color: "rgb(var(--paper-50))",
                border: "1px solid rgb(255 255 255 / 0.18)",
                padding: "12px 20px",
                fontSize: 14,
              }}
            >
              Sign in →
            </Link>
          </div>
          <p
            style={{
              fontSize: 12,
              color: "rgb(var(--ink-300))",
              margin: "0 0 48px",
              fontFamily: "var(--font-mono)",
            }}
          >
            One click. We create the workspace from your Slack team.
          </p>

          <div
            style={{
              display: "flex",
              gap: 24,
              alignItems: "center",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              color: "rgb(var(--ink-300))",
              flexWrap: "wrap",
            }}
          >
            <span>✓ BYO Anthropic key</span>
            <span>✓ Slack OAuth, workspace-scoped</span>
            <span>✓ 25 users · 25 agents</span>
          </div>
        </div>

        {/* Animated setup-then-use flow */}
        <HeroFlow />
      </div>
    </section>
  );
}

export default function Landing() {
  return (
    <div>
      <LandingNav />
      <Hero />

      <HowItWorks />
      <Features />
      <InAction />
      <Commands />
      <PowerloomCallout />
      <CTA />
      <Footer />
    </div>
  );
}
