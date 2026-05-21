# Relay v2 — local dev launcher.
# Brings up Postgres, the FastAPI gateway, and the Next.js UI in three
# separate windows so you can iterate without juggling tabs.
#
# Each child window persists independently. Ctrl-C inside a window
# stops that one service.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host ""
Write-Host "Relay v2 — bringing up dev stack..." -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Docker / Postgres
# ---------------------------------------------------------------------------

Write-Host "[1/3] Postgres" -ForegroundColor Yellow

$pg = docker ps --filter "name=relay-v2-postgres-1" --filter "status=running" --format "{{.Names}}"
if (-not $pg) {
    Write-Host "  starting docker compose..."
    Push-Location $root
    docker compose up -d postgres | Out-Null
    Pop-Location
} else {
    Write-Host "  already running" -ForegroundColor Green
}

# Wait for Postgres to accept connections
$attempts = 0
$maxAttempts = 30
do {
    Start-Sleep -Milliseconds 500
    $ready = docker exec relay-v2-postgres-1 pg_isready -U relay -d relay_dev 2>$null
    $attempts++
} while ($ready -notmatch "accepting connections" -and $attempts -lt $maxAttempts)

if ($attempts -ge $maxAttempts) {
    Write-Host "  Postgres did not become ready in 15s — check docker logs relay-v2-postgres-1" -ForegroundColor Red
    exit 1
}
Write-Host "  Postgres ready on :5432" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. API
# ---------------------------------------------------------------------------

Write-Host "[2/3] API" -ForegroundColor Yellow

$apiPath = Join-Path $root "api"
$apiVenv = Join-Path $apiPath ".venv\Scripts\python.exe"
if (-not (Test-Path $apiVenv)) {
    Write-Host "  api/.venv not found. Run from api/: python -m venv .venv && .venv\Scripts\pip install -e '.[dev]'" -ForegroundColor Red
    exit 1
}

# Make sure migrations are up to date — quick + idempotent
Push-Location $apiPath
& $apiVenv -m alembic upgrade head 2>&1 | Out-Host
Pop-Location

# Launch uvicorn in a new window
$apiCmd = "Set-Location '$apiPath'; & '$apiVenv' -m uvicorn relay_api.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $apiCmd -WindowStyle Normal | Out-Null
Write-Host "  API launching in a new window — http://localhost:8000" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. UI
# ---------------------------------------------------------------------------

Write-Host "[3/3] UI" -ForegroundColor Yellow

$uiPath = Join-Path $root "ui"
if (-not (Test-Path (Join-Path $uiPath "node_modules"))) {
    Write-Host "  ui/node_modules not found — running npm install..." -ForegroundColor Yellow
    Push-Location $uiPath
    npm install --silent
    Pop-Location
}

$uiCmd = "Set-Location '$uiPath'; npm run dev"
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $uiCmd -WindowStyle Normal | Out-Null
Write-Host "  UI launching in a new window — http://localhost:3006" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "Relay v2 dev stack up. Watch the two child windows for logs." -ForegroundColor Cyan
Write-Host ""
Write-Host "  UI:  http://localhost:3006" -ForegroundColor White
Write-Host "  API: http://localhost:8000/api/health" -ForegroundColor White
Write-Host ""
Write-Host "Ctrl-C in either child window to stop that service." -ForegroundColor DarkGray
Write-Host "docker compose down  (from this dir) to stop Postgres." -ForegroundColor DarkGray
Write-Host ""
