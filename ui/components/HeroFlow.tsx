"use client";

/**
 * Animated hero — "setup-then-use, in one window".
 *
 * One Slack-style window frame for the whole story:
 *   Phase 1 (setup): three rows tick on in sequence — Slack connect,
 *     Anthropic key paste, first agent added.
 *   Phase 2 (use): rows fade up & out, a channel header materializes,
 *     a user message lands, /relay command, processing pulse, reply.
 *
 * Loops every ~12s. All motion is opacity + small translate; no busy
 * chrome. The brief is elegance through simplicity.
 */
import { CheckCircle2, KeyRound, Slack, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

/* Step numbers — each entry in TIMELINE pushes us forward one beat. */
const SETUP_END = 7; // ≤ 7 → setup view, ≥ 8 → use view
const TIMELINE: Array<[step: number, atMs: number]> = [
  [1, 400],     // row 1 appears
  [2, 1300],    // row 1 ticked (Slack connected)
  [3, 1800],    // row 2 appears
  [4, 3000],    // row 2 ticked (key pasted)
  [5, 3500],    // row 3 appears
  [6, 4600],    // row 3 ticked (agent added)
  [7, 5300],    // "Connected." chip
  [8, 6300],    // setup fades out → channel header in
  [9, 7100],    // user message
  [10, 8000],   // /relay command
  [11, 9000],   // bot processing pulse
  [12, 10200],  // bot reply
];
const LOOP_MS = 12500;

export function HeroFlow() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    let handles: ReturnType<typeof setTimeout>[] = [];
    const run = () => {
      handles.forEach(clearTimeout);
      handles = TIMELINE.map(([s, t]) => setTimeout(() => setStep(s), t));
    };
    run();
    const restart = setInterval(() => {
      setStep(0);
      run();
    }, LOOP_MS);
    return () => {
      handles.forEach(clearTimeout);
      clearInterval(restart);
    };
  }, []);

  const inSetup = step <= SETUP_END;

  return (
    <div className="rl-hero-flow">
      {/* window chrome */}
      <div className="rl-hero-flow-chrome">
        <span className="rl-hero-flow-traffic" style={{ background: "#FF5F57" }} />
        <span className="rl-hero-flow-traffic" style={{ background: "#FEBC2E" }} />
        <span className="rl-hero-flow-traffic" style={{ background: "#28C840" }} />
        <div className="rl-hero-flow-title">
          {inSetup ? "setting up acme · relay" : "# prod-incidents · acme.slack.com"}
        </div>
        <div style={{ width: 60 }} />
      </div>

      {/* body — two views in the same frame, opacity-swapped */}
      <div className="rl-hero-flow-body">
        <div
          className="rl-hero-flow-view"
          style={{
            opacity: inSetup ? 1 : 0,
            transform: inSetup ? "translateY(0)" : "translateY(-8px)",
            pointerEvents: inSetup ? "auto" : "none",
          }}
        >
          <SetupView step={step} />
        </div>
        <div
          className="rl-hero-flow-view"
          style={{
            opacity: inSetup ? 0 : 1,
            transform: inSetup ? "translateY(8px)" : "translateY(0)",
            pointerEvents: inSetup ? "none" : "auto",
          }}
        >
          <UseView step={step} />
        </div>
      </div>
    </div>
  );
}

/* ─── Setup view ──────────────────────────────────────────────────── */

function SetupView({ step }: { step: number }) {
  const r1Visible = step >= 1;
  const r1Done = step >= 2;
  const r2Visible = step >= 3;
  const r2Done = step >= 4;
  const r3Visible = step >= 5;
  const r3Done = step >= 6;
  const allDone = step >= 7;

  return (
    <div className="rl-hero-flow-setup">
      <div className="rl-hero-flow-setup-label">Three pieces. Two minutes.</div>

      <SetupRow
        n="01"
        icon={<Slack size={14} />}
        title="Slack workspace"
        value={r1Done ? "acme.slack.com" : "Connect via OAuth"}
        visible={r1Visible}
        done={r1Done}
      />
      <SetupRow
        n="02"
        icon={<KeyRound size={14} />}
        title="Anthropic key"
        value={
          r2Done ? (
            <span className="mono" style={{ fontSize: 12.5 }}>
              sk-ant-api03-•••••••••••
            </span>
          ) : (
            "Paste sk-ant-…"
          )
        }
        visible={r2Visible}
        done={r2Done}
      />
      <SetupRow
        n="03"
        icon={<Sparkles size={14} />}
        title="First agent"
        value={
          r3Done ? (
            <span className="mono" style={{ fontSize: 12.5 }}>
              @relay runbook
            </span>
          ) : (
            "Pick a name"
          )
        }
        visible={r3Visible}
        done={r3Done}
      />

      <div
        className="rl-hero-flow-connected"
        style={{
          opacity: allDone ? 1 : 0,
          transform: allDone ? "translateY(0)" : "translateY(4px)",
        }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: "rgb(var(--relay-500))",
            boxShadow: "0 0 10px rgb(var(--relay-500))",
          }}
        />
        Connected. Mention <span className="mono">@relay</span> in any channel.
      </div>
    </div>
  );
}

function SetupRow({
  n,
  icon,
  title,
  value,
  visible,
  done,
}: {
  n: string;
  icon: React.ReactNode;
  title: string;
  value: React.ReactNode;
  visible: boolean;
  done: boolean;
}) {
  return (
    <div
      className="rl-hero-flow-row"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(6px)",
      }}
    >
      <div className="rl-hero-flow-row-n">{n}</div>
      <div
        className="rl-hero-flow-row-icon"
        style={{
          background: done ? "rgb(var(--relay-500) / 0.12)" : "#F1EFE9",
          color: done ? "rgb(var(--relay-700))" : "#4A515C",
          transition: "background 320ms, color 320ms",
        }}
      >
        {icon}
      </div>
      <div className="rl-hero-flow-row-text">
        <div style={{ fontSize: 12, fontWeight: 600, color: "#0F1419" }}>{title}</div>
        <div
          style={{
            fontSize: 12,
            color: done ? "#0F1419" : "#838A95",
            marginTop: 2,
            transition: "color 320ms",
          }}
        >
          {value}
        </div>
      </div>
      <div
        className="rl-hero-flow-row-check"
        style={{
          opacity: done ? 1 : 0,
          transform: done ? "scale(1)" : "scale(0.7)",
          transition: "opacity 240ms, transform 240ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        <CheckCircle2 size={16} color="rgb(var(--relay-500))" />
      </div>
    </div>
  );
}

/* ─── Use view ────────────────────────────────────────────────────── */

function UseView({ step }: { step: number }) {
  const showUser = step >= 9;
  const showCmd = step >= 10;
  const showProcessing = step >= 11 && step < 12;
  const showReply = step >= 12;

  return (
    <div className="rl-hero-flow-use">
      {showUser && (
        <MessageRow
          author="Maya Rodriguez"
          avatar="MR"
          avatarColor="#36C5F0"
          time="10:42"
        >
          Pager just blew up — 5xx spike on <strong>checkout-svc</strong>.
        </MessageRow>
      )}

      {showCmd && (
        <MessageRow
          author="Maya Rodriguez"
          avatar="MR"
          avatarColor="#36C5F0"
          time="10:43"
        >
          <span className="rl-hero-flow-cmd">/relay runbook investigate</span>
        </MessageRow>
      )}

      {showProcessing && (
        <div className="rl-hero-flow-processing">
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 4,
              background: "rgb(var(--relay-500))",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              fontSize: 13,
              flexShrink: 0,
            }}
          >
            R
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: "#0F1419" }}>
              @runbook is investigating…
            </div>
            <div
              style={{
                fontSize: 11,
                color: "#4A515C",
                marginTop: 2,
                fontFamily: "var(--font-mono)",
              }}
            >
              diffing recent deploys
            </div>
          </div>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "rgb(var(--relay-500))",
              animation: "rl-pulse 1.2s ease-in-out infinite",
            }}
          />
        </div>
      )}

      {showReply && (
        <MessageRow
          author="Relay · @runbook"
          avatar="R"
          avatarColor="rgb(var(--relay-500))"
          time="10:48"
          app
        >
          Likely cause: deploy{" "}
          <span className="rl-hero-flow-code">4a8c2e1</span> at 10:38 removed{" "}
          <span className="rl-hero-flow-code">idempotency_key</span>. Recommend rollback.
        </MessageRow>
      )}
    </div>
  );
}

function MessageRow({
  author,
  avatar,
  avatarColor,
  time,
  app,
  children,
}: {
  author: string;
  avatar: string;
  avatarColor: string;
  time: string;
  app?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="rl-hero-flow-msg">
      <div
        className="rl-hero-flow-msg-avatar"
        style={{ background: avatarColor }}
      >
        {avatar}
      </div>
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span
            style={{
              fontSize: 13.5,
              fontWeight: 700,
              color: "#0F1419",
              letterSpacing: "-0.01em",
            }}
          >
            {author}
          </span>
          {app && (
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                padding: "1px 5px",
                borderRadius: 3,
                background: "rgb(var(--relay-500) / 0.12)",
                color: "rgb(var(--relay-700))",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              APP
            </span>
          )}
          <span style={{ fontSize: 11, color: "#838A95" }}>{time}</span>
        </div>
        <div
          style={{
            fontSize: 13.5,
            lineHeight: 1.5,
            color: "#0F1419",
            marginTop: 1,
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
