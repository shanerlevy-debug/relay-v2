# relay-bridge

The multi-tenant Slack ↔ Claude Managed Agents bridge process. Long-lived
Socket Mode connection that delivers events from N tenant Slack workspaces
(installed via the API's `/api/oauth/slack/start` flow) and routes each
one to the workspace's configured agent using the workspace's own
Anthropic API key (BYOK).

## Architecture

```
       N Slack workspaces (all installed against ONE Slack App)
                       │
                       │  Socket Mode (single xapp- App-Level Token)
                       ▼
              ┌─────────────────────┐
              │  relay-bridge       │
              │  ─ authorize cb     │ team_id → bot_token (decrypt envelope)
              │  ─ on_app_mention   │ slug -> agent (Postgres)
              │  ─ on_message       │ thread pin (slack_threads)
              │  ─ on_slash         │ BYOK key (decrypt envelope)
              │  ─ CMA invocation   │ session reuse (Postgres)
              │  ─ audit log writes │
              └──────────┬──────────┘
                         │
                  ┌──────┴──────┐
                  ▼             ▼
            Anthropic API   Postgres
            (per-workspace  (shared with
             BYOK key)       relay-api)
```

## Install (local dev)

```powershell
# From D:\Relay\relay-v2\bridge\
python -m venv .venv
.venv\Scripts\pip install -e ..\api          # relay_api package
.venv\Scripts\pip install -e .[dev]           # this package
```

## Run

```powershell
# Make sure Postgres is up + migrations applied (see api/ README)
# Set RELAY_SLACK_APP_TOKEN in .env first
.venv\Scripts\python -m relay_bridge.main
```

## Tests

```powershell
.venv\Scripts\python -m pytest
```

Tests fully mock the Slack Web Client + Anthropic SDK — no network calls.
A live Postgres is required for the `dbtest`-marked tests (set
`DATABASE_URL` or run `docker compose up -d postgres` from the repo root).
