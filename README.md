# Relay v2 — multi-tenant Slack ↔ Claude Managed Agents pop-up

Production at **relayed.live** (when deployed). This is the monorepo for the multi-tenant version of [Relay v1](https://github.com/shanerlevy-debug/Relay).

Read the buildout plan first: [`../RELAY-V2-PLAN.md`](../RELAY-V2-PLAN.md) (outside the repo, in `D:\Relay\`).

## Layout

```
relay-v2/
├── api/              FastAPI gateway — auth, install flow, agents CRUD, audit
│   ├── relay_api/
│   │   ├── core/     config, errors, logging
│   │   ├── db/       SQLAlchemy session + (later) models
│   │   ├── routes/   FastAPI routers
│   │   └── services/ business logic (envelope encryption, oauth, etc.)
│   ├── alembic/      database migrations
│   ├── tests/
│   ├── pyproject.toml
│   └── alembic.ini
│
├── ui/               Next.js admin console — login, settings, agents page
│                     (scaffolded later; lift from Powerloom's AppShell + ui/*)
│
├── bridge/           Multi-tenant Slack Socket Mode bridge
│                     (lifted + adapted from D:/Relay/bridge/ in week 2)
│
├── infra/            Lightsail provisioning + systemd units + nginx config
├── docs/             Architecture, ADRs, operational notes
├── scripts/          dev helpers (generate-master-key, etc.)
├── docker-compose.yml   Postgres for local dev
└── .env.example
```

## Stack

- **API:** Python 3.12, FastAPI, SQLAlchemy 2 + psycopg3, Alembic, Pydantic v2, structlog, AES-256-GCM envelope encryption
- **UI:** Next.js + React + Tailwind (week 3)
- **Bridge:** Python 3.12, Slack Bolt, anthropic SDK (lifted from v1, adapted for multi-tenant in week 2)
- **DB:** Postgres 16
- **Host:** Lightsail small_3_0 ($10/mo) — nginx fronting three systemd services

## Local dev quickstart

```powershell
# 1. Bring up Postgres
docker compose up -d postgres

# 2. Generate a dev master key (32 bytes, base64). One-time per machine.
python scripts/generate-master-key.py

# 3. Set up the API
cd api
python -m venv .venv
.venv\Scripts\pip install -e .
copy ..\.env.example ..\.env
# Paste the master key from step 2 into .env as RELAY_MASTER_KEY_B64

# 4. Run migrations (none yet, but the command is ready)
.venv\Scripts\alembic upgrade head

# 5. Start the API
.venv\Scripts\uvicorn relay_api.main:app --reload --port 8000
```

Then `curl http://localhost:8000/api/health` should return `{"status":"ok", "db":"ok"}`.

## What's done / what's next

See task tracker in the session or `../RELAY-V2-PLAN.md` §7 for the week-by-week schedule.

**Done (week 1 day 1):**
- Monorepo scaffolded
- FastAPI skeleton lifted from Powerloom (skinny — no schema-version gate, no super-admin, no slowapi)
- AES-256-GCM envelope encryption as free functions (decoupled from any ORM model)
- Postgres via docker-compose
- `/api/health` returns 200 with DB check

**Next:**
- Database models + initial migration (`workspaces`, `users`, `audit_log`, `invites`, `enterprise_requests`, `slack_threads`)
- Lift Slack OAuth install flow from Powerloom
- Lift password auth + invite flow
- Lift Next.js UI shell

## Reference

- Architectural framing & strategy: [`../RELAY-V2-PLAN.md`](../RELAY-V2-PLAN.md)
- v1 (single-tenant, shipped): [`../bridge/`](../bridge/) and https://github.com/shanerlevy-debug/Relay
- Powerloom (the main establishment): https://github.com/shanerlevy-debug/Powerloom — read-only for research at `../powerloom-research/`
