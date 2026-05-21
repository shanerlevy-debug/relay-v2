# Relay UI

Next.js 16 (App Router) + React 19 + TypeScript. Design tokens lifted
from `D:\Relay\relay-mockup-extracted\styles\` (Shane's designer output);
component primitives lifted from the same mockup with JSX→TSX conversion.

## Run

```powershell
npm install
npm run dev
```

Visit http://localhost:3000.

The dev server proxies `/api/*` to the FastAPI gateway at `http://localhost:8000`
via `next.config.mjs` rewrites. Make sure the API is running (`uvicorn relay_api.main:app`
from `../api`).

## Layout

```
ui/
├── app/                     Next.js App Router pages
│   ├── layout.tsx           Root layout — fonts + global CSS
│   ├── page.tsx             Landing page (/)
│   ├── login/               /login
│   └── (console)/           Authenticated route group (sidebar shell)
├── components/
│   ├── RelayMark.tsx        The logo
│   ├── AppShell.tsx         Console sidebar + main (auth pages)
│   └── ui/                  Button, Card, StatusBadge, PageHeader, Eyebrow
├── lib/
│   └── api.ts               Typed fetch wrapper for the FastAPI gateway
├── styles/
│   ├── tokens.css           Powerloom design tokens (warm paper + Inter)
│   └── relay.css            Relay overrides (coral #E2574F, Fraunces italic)
└── public/                  Static assets (logo, favicon)
```

## Design decisions

See `D:\Relay\RELAY-V2-UI-DESIGN.md` (the original plan) and the memory
file `project_ui_design_decisions.md` (what got locked in after reviewing
the mockup): coral `#E2574F` accent, sidebar layout, `/relay` + `@relay`
naming, scope kept at pop-up (no multi-workspace / no RBAC / no sessions
history — those land in Powerloom).
