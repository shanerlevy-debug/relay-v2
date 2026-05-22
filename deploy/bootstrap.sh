#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 22.04 Lightsail instance.
# Run as root or via sudo. Idempotent — safe to re-run.
#
# After completion:
#   1. Edit /etc/relay/secrets.env (Slack OAuth, etc.) — most values are
#      pre-filled by this script; you only paste the Slack credentials.
#   2. Run TLS bootstrap: `sudo certbot --nginx -d relayed.live`
#   3. Start the services: `sudo systemctl enable --now relay-api relay-bridge relay-ui`

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/shanerlevy-debug/relay-v2.git}"
APP_DIR=/opt/relay
ETC_DIR=/etc/relay
VAR_DIR=/var/lib/relay
LOG_DIR=/var/log/relay
REDEPLOY_LOG=/var/log/relay/redeploy.log

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "bootstrap.sh must run as root (try: sudo $0)" >&2
    exit 1
fi

echo "==> [1/10] System packages"
apt-get update -qq
# Ubuntu 22.04 ships Python 3.10; we need 3.12. Add the deadsnakes PPA.
apt-get install -y -qq software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -qq
apt-get install -y -qq \
    git curl ca-certificates build-essential \
    python3.12 python3.12-venv python3.12-dev python3-pip \
    postgresql postgresql-contrib \
    nginx \
    certbot python3-certbot-nginx \
    ufw

# Node.js 22 LTS via NodeSource (Ubuntu 22.04 ships an older version)
if ! command -v node >/dev/null 2>&1 || [ "$(node --version | grep -oP 'v\K\d+')" -lt 20 ]; then
    echo "  installing Node.js 22 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y -qq nodejs
fi

echo "==> [2/10] Service user + dirs"
if ! id relay >/dev/null 2>&1; then
    useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin relay
fi
mkdir -p "$APP_DIR" "$ETC_DIR" "$VAR_DIR" "$VAR_DIR/agent-icons" "$LOG_DIR"
chown -R relay:relay "$APP_DIR" "$VAR_DIR" "$LOG_DIR"
# nginx needs traversal to read agent-icons; relay user owns the files,
# but world-readable so the nginx worker (www-data) can serve them.
chmod 755 "$VAR_DIR" "$VAR_DIR/agent-icons"
# /etc/relay is root-owned but relay-group-traversable so the relay
# user can read secrets.env (mode 0640 root:relay) inside it.
chown root:relay "$ETC_DIR"
chmod 750 "$ETC_DIR"
touch "$REDEPLOY_LOG"
chown relay:relay "$REDEPLOY_LOG"

echo "==> [3/10] Clone repo (or pull if already present)"
if [ ! -d "$APP_DIR/.git" ]; then
    sudo -u relay git clone --quiet "$REPO_URL" "$APP_DIR"
else
    sudo -u relay git -C "$APP_DIR" fetch --quiet origin main
    sudo -u relay git -C "$APP_DIR" reset --quiet --hard origin/main
fi

echo "==> [4/10] Postgres: create user + database"
# Use peer auth via sudo -u postgres. The first run sets the password; subsequent
# runs read the existing one out of secrets.env so we don't rotate it.
PG_PW_PLAIN=""
if [ -f "$ETC_DIR/secrets.env" ] && grep -q '^DATABASE_URL=' "$ETC_DIR/secrets.env"; then
    PG_PW_PLAIN=$(grep '^DATABASE_URL=' "$ETC_DIR/secrets.env" | sed -E 's|^DATABASE_URL=postgresql\+psycopg://relay:([^@]+)@.*|\1|')
fi
if [ -z "$PG_PW_PLAIN" ]; then
    PG_PW_PLAIN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
fi

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='relay'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE ROLE relay LOGIN PASSWORD '$PG_PW_PLAIN'"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='relay'" | grep -q 1 || \
    sudo -u postgres createdb -O relay relay

# Make sure the password stored matches (re-set on every run; idempotent).
sudo -u postgres psql -c "ALTER ROLE relay WITH PASSWORD '$PG_PW_PLAIN'" >/dev/null

# Tune Postgres for the tight 1 GB box. micro_3_0 has limited RAM; we
# share it with API + UI + Bridge.
PG_CONF="/etc/postgresql/$(ls /etc/postgresql/ | head -1)/main/postgresql.conf"
if [ -f "$PG_CONF" ]; then
    sed -i 's/^#*shared_buffers = .*/shared_buffers = 128MB/' "$PG_CONF"
    sed -i 's/^#*effective_cache_size = .*/effective_cache_size = 256MB/' "$PG_CONF"
    sed -i 's/^#*work_mem = .*/work_mem = 4MB/' "$PG_CONF"
    sed -i 's/^#*maintenance_work_mem = .*/maintenance_work_mem = 32MB/' "$PG_CONF"
    sed -i 's/^#*max_connections = .*/max_connections = 50/' "$PG_CONF"
    systemctl restart postgresql
fi

echo "==> [5/10] Secrets bootstrap"
if [ ! -f "$ETC_DIR/secrets.env" ]; then
    # First run — generate fresh JWT secret + master key, fill in Postgres URL,
    # leave Slack credentials blank for the operator to paste in.
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
    MASTER_KEY=$(python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())")
    cp "$APP_DIR/deploy/secrets.env.example" "$ETC_DIR/secrets.env"
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://relay:${PG_PW_PLAIN}@127.0.0.1:5432/relay|" "$ETC_DIR/secrets.env"
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" "$ETC_DIR/secrets.env"
    sed -i "s|^RELAY_MASTER_KEY_B64=.*|RELAY_MASTER_KEY_B64=${MASTER_KEY}|" "$ETC_DIR/secrets.env"
    chown root:relay "$ETC_DIR/secrets.env"
    chmod 640 "$ETC_DIR/secrets.env"
    echo "    WROTE $ETC_DIR/secrets.env — paste Slack credentials before starting services"
else
    echo "    $ETC_DIR/secrets.env already exists, leaving alone"
    # Ensure DATABASE_URL has the right password (in case we just rotated)
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://relay:${PG_PW_PLAIN}@127.0.0.1:5432/relay|" "$ETC_DIR/secrets.env"
fi

echo "==> [6/10] API venv + deps"
if [ ! -d "$APP_DIR/api/.venv" ]; then
    sudo -u relay python3.12 -m venv "$APP_DIR/api/.venv"
fi
sudo -u relay "$APP_DIR/api/.venv/bin/pip" install --quiet --upgrade pip
sudo -u relay "$APP_DIR/api/.venv/bin/pip" install --quiet -e "$APP_DIR/api"

echo "==> [7/10] Bridge venv + deps (depends on relay-api editable)"
if [ ! -d "$APP_DIR/bridge/.venv" ]; then
    sudo -u relay python3.12 -m venv "$APP_DIR/bridge/.venv"
fi
sudo -u relay "$APP_DIR/bridge/.venv/bin/pip" install --quiet --upgrade pip
sudo -u relay "$APP_DIR/bridge/.venv/bin/pip" install --quiet -e "$APP_DIR/api" -e "$APP_DIR/bridge"

echo "==> [8/10] UI deps + production build"
cd "$APP_DIR/ui"
sudo -u relay npm install --silent --no-audit --no-fund
sudo -u relay npm run build --silent
cd - >/dev/null

echo "==> [9/10] Database migrations"
sudo -u relay bash -c "set -a && source $ETC_DIR/secrets.env && set +a && cd $APP_DIR/api && .venv/bin/alembic upgrade head"

echo "==> [10/10] systemd units + nginx + firewall"
install -m 644 "$APP_DIR/deploy/relay-api.service" /etc/systemd/system/
install -m 644 "$APP_DIR/deploy/relay-bridge.service" /etc/systemd/system/
install -m 644 "$APP_DIR/deploy/relay-ui.service" /etc/systemd/system/
systemctl daemon-reload

install -m 644 "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/relay
ln -sf /etc/nginx/sites-available/relay /etc/nginx/sites-enabled/relay
rm -f /etc/nginx/sites-enabled/default

# certbot's ACME challenge dir
mkdir -p /var/www/certbot

# Firewall — allow 80, 443, SSH
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null

# Validate nginx config (without TLS certs yet, the HTTPS server block will
# fail — that's expected on first bootstrap). Hold nginx restart until
# certbot has provisioned certs.
if [ -f "/etc/letsencrypt/live/relayed.live/fullchain.pem" ]; then
    nginx -t && systemctl reload nginx
    echo "  nginx reloaded with TLS"
else
    echo "  TLS not yet provisioned — run: certbot --nginx -d relayed.live"
fi

echo ""
echo "==> Bootstrap complete."
echo ""
echo "Next steps (in order):"
echo "  1. Paste Slack credentials into /etc/relay/secrets.env:"
echo "       OAUTH_SLACK_CLIENT_ID"
echo "       OAUTH_SLACK_CLIENT_SECRET"
echo "       RELAY_SLACK_APP_TOKEN"
echo "  2. Provision TLS:    sudo certbot --nginx -d relayed.live"
echo "  3. Start services:   sudo systemctl enable --now relay-api relay-bridge relay-ui"
echo "  4. Tail logs:        sudo journalctl -u relay-api -u relay-bridge -u relay-ui -f"
