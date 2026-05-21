# Relay v2 — architecture overview

The full strategic + buildout document lives one level up, outside the repo:
[`../../RELAY-V2-PLAN.md`](../../RELAY-V2-PLAN.md).

This doc is the short version that lives WITH the code.

## The shape

```
                     Slack workspaces (N tenants)
                            │
                            ▼  Socket Mode (one app, N workspaces)
                ┌──────────────────────────────┐
   browsers ──► │  nginx :443                  │
                │   ├─► UI  :3000 (Next.js)    │
                │   └─► API :8000 (FastAPI) ◄──┤ tenant lookup by team_id
                │  bridge (Slack Bolt + CMA SDK) │
                └──────────────────────────────┘
                            │
                            ▼
                       Postgres (local)
```

All four processes on one Lightsail box (`small_3_0`, 2 GB, $10/mo). nginx
fronts both UI and API. Bridge talks to the API gateway over a localhost
socket for tenant lookups + agent registry reads.

## The deliberate ceiling

Read [`../../RELAY-V2-PLAN.md`](../../RELAY-V2-PLAN.md) §10 for the full list.
TL;DR: no SSO, no SOC2, no MCP fleet, no memory, no audit chain, ≤25 users
+ ≤25 agents per workspace. Hitting any of these triggers the
"Request Enterprise" CTA, which is a lead-gen funnel into Powerloom.

## Multi-tenancy boundary

`workspace_id` is the only tenant identifier in this codebase. Powerloom's
OU + Principal + RBAC complex stays out — see plan §10. Server-side
authorization is one line: `if request.workspace_id != target.workspace_id: 403`.

## Encrypted secrets at rest

All tenant-supplied tokens (Slack bot tokens, Anthropic BYO keys) are
AES-256-GCM-enveloped on their row, with the row's UUID as the AAD. Master
key lives in `RELAY_MASTER_KEY_B64` (env var, loaded from
`/etc/relay/master.key` chmod 0400 in prod). See `relay_api/services/envelope.py`.

## Migration triggers

We stay on Lightsail until ANY of:
- A tenant asks about Enterprise / SOC2 / HA / SSO → they go to Powerloom
- Sustained CPU > 75% for a week → next box size up
- Postgres > 1 GB on-disk → split to RDS db.t4g.micro

See plan §9 for the full ladder.
