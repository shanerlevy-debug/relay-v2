"use client";

/**
 * Animated Slack mockup that plays on the landing hero. Lifted (and
 * re-typed) from the designer's `landing.jsx` HeroSlackPreview component.
 * Loops on a ~11s cycle: Maya's message -> /relay command -> bot
 * processing -> bot reply.
 */
import { useEffect, useState } from "react";

interface MsgProps {
  author: string;
  avatar: string;
  color: string;
  ts: string;
  show: boolean;
  app?: boolean;
  children: React.ReactNode;
}

function Msg({ author, avatar, color, ts, show, app, children }: MsgProps) {
  if (!show) return null;
  return (
    <div
      style={{
        padding: "8px 16px",
        display: "grid",
        gridTemplateColumns: "36px 1fr",
        gap: 10,
        animation: "rl-event-enter 240ms",
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 6,
          background: color,
          color: "#fff",
          fontSize: 13,
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {avatar}
      </div>
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span
            style={{
              fontSize: 14,
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
          <span style={{ fontSize: 11, color: "#838A95" }}>{ts}</span>
        </div>
        <div
          style={{
            fontSize: 14,
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

export function HeroSlackPreview() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timeline: [number, number][] = [
      [0, 600],
      [1, 1600],
      [2, 2200],
      [3, 4000],
      [4, 5400],
    ];
    let handles: ReturnType<typeof setTimeout>[] = [];
    const run = () => {
      handles.forEach(clearTimeout);
      handles = timeline.map(([s, t]) => setTimeout(() => setStep(s), t));
    };
    run();
    const restart = setInterval(() => {
      setStep(0);
      run();
    }, 11000);
    return () => {
      handles.forEach(clearTimeout);
      clearInterval(restart);
    };
  }, []);

  return (
    <div
      style={{
        position: "relative",
        background: "rgb(var(--paper-100))",
        borderRadius: 12,
        border: "1px solid rgb(255 255 255 / 0.08)",
        overflow: "hidden",
        boxShadow: "0 30px 80px rgba(0,0,0,0.4), 0 8px 16px rgba(0,0,0,0.3)",
        minHeight: 460,
      }}
    >
      {/* Window chrome */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          background: "#E8E5DD",
          borderBottom: "1px solid #D4D1C8",
        }}
      >
        <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#FF5F57" }} />
        <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#FEBC2E" }} />
        <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#28C840" }} />
        <div
          style={{
            flex: 1,
            textAlign: "center",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "#4A515C",
          }}
        >
          # prod-incidents · acme.slack.com
        </div>
        <div style={{ width: 60 }} />
      </div>

      {/* Messages */}
      <div style={{ background: "#FFFFFF", padding: "10px 0", color: "#0F1419", minHeight: 410 }}>
        <Msg author="Maya Rodriguez" avatar="MR" color="#36C5F0" ts="10:42" show={step >= 0}>
          Pager just blew up — 5xx spike on <strong>checkout-svc</strong>, started ~5 min ago.
        </Msg>

        <Msg author="Maya Rodriguez" avatar="MR" color="#36C5F0" ts="10:43" show={step >= 1}>
          <span
            style={{
              background: "rgb(var(--relay-500) / 0.12)",
              color: "rgb(var(--relay-700))",
              padding: "1px 5px",
              borderRadius: 3,
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            /relay runbook investigate checkout-svc 5xx spike
          </span>
        </Msg>

        {step >= 2 && (
          <div
            style={{
              margin: "8px 16px",
              padding: "12px 14px",
              background: "rgb(var(--relay-500) / 0.06)",
              border: "1px solid rgb(var(--relay-500) / 0.18)",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              gap: 12,
              animation: "rl-event-enter 240ms",
            }}
          >
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
                {step === 2
                  ? "querying datadog…"
                  : step === 3
                    ? "diffing recent deploys…"
                    : "drafting summary…"}
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

        {step >= 4 && (
          <div style={{ animation: "rl-event-enter 320ms" }}>
            <Msg author="Relay · @runbook" avatar="R" color="rgb(var(--relay-500))" ts="10:48" app show>
              <div style={{ fontSize: 13.5, lineHeight: 1.55 }}>
                Likely cause: deploy{" "}
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    background: "#F1EFE9",
                    padding: "0 4px",
                    borderRadius: 3,
                  }}
                >
                  4a8c2e1
                </span>{" "}
                at 10:38:02Z removed{" "}
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    background: "#F1EFE9",
                    padding: "0 4px",
                    borderRadius: 3,
                  }}
                >
                  idempotency_key
                </span>{" "}
                from{" "}
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    background: "#F1EFE9",
                    padding: "0 4px",
                    borderRadius: 3,
                  }}
                >
                  stripe_client.rb
                </span>
                . 18/20 error logs match. Recommend rollback.
              </div>
              <div style={{ marginTop: 10, display: "flex", gap: 6 }}>
                <span
                  style={{
                    fontSize: 11.5,
                    padding: "4px 10px",
                    background: "rgb(var(--relay-500))",
                    color: "#fff",
                    borderRadius: 4,
                    fontWeight: 500,
                  }}
                >
                  Open revert PR
                </span>
                <span
                  style={{
                    fontSize: 11.5,
                    padding: "4px 10px",
                    background: "#F1EFE9",
                    color: "#0F1419",
                    borderRadius: 4,
                    fontWeight: 500,
                    border: "1px solid #D4D1C8",
                  }}
                >
                  Page on-call
                </span>
              </div>
            </Msg>
          </div>
        )}
      </div>
    </div>
  );
}
