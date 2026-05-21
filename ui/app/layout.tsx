import type { Metadata } from "next";
import { Fraunces, Inter, JetBrains_Mono } from "next/font/google";

import "../styles/tokens.css";
import "../styles/relay.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans-loaded",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono-loaded",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["italic"],
  variable: "--font-serif-loaded",
});

export const metadata: Metadata = {
  title: "Relay — Slack ↔ Claude managed agents",
  description:
    "Your Claude agents, one mention away. @relay in any channel; answers land in the thread. BYO Anthropic key, up to 25 agents per workspace.",
  icons: [{ rel: "icon", url: "/relay-logo-512.png" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      data-theme="light"
      className={`${inter.variable} ${mono.variable} ${fraunces.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
