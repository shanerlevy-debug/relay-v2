#!/usr/bin/env bash
# Pull latest from main + apply migrations + rebuild UI + restart services.
# Idempotent — safe to run repeatedly. Run as root or via sudo.
#
# Logs every step to /var/log/relay/redeploy.log so you can audit
# upgrades after the fact.

set -euo pipefail

APP_DIR=/opt/relay
LOG=/var/log/relay/redeploy.log
ETC_DIR=/etc/relay

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "redeploy.sh must run as root (try: sudo $0)" >&2
    exit 1
fi

ts() { date -Is; }

{
    echo ""
    echo "=========================="
    echo "$(ts) redeploy starting"
    echo "=========================="

    # --- 1. Pull latest source --------------------------------------------
    BEFORE=$(sudo -u relay git -C "$APP_DIR" rev-parse HEAD)
    sudo -u relay git -C "$APP_DIR" fetch --quiet origin main
    sudo -u relay git -C "$APP_DIR" reset --quiet --hard origin/main
    AFTER=$(sudo -u relay git -C "$APP_DIR" rev-parse HEAD)

    if [ "$BEFORE" = "$AFTER" ]; then
        echo "$(ts) no new commits — skipping rebuild + restart"
        exit 0
    fi

    echo "$(ts) updated: $BEFORE -> $AFTER"
    CHANGED=$(sudo -u relay git -C "$APP_DIR" diff --name-only "$BEFORE..$AFTER")
    echo "$(ts) changed files:"
    echo "$CHANGED" | sed 's/^/    /'

    # --- 2. Update Python venvs if requirements drifted ------------------
    if echo "$CHANGED" | grep -qE '^api/pyproject.toml$'; then
        echo "$(ts) api/pyproject.toml changed -- reinstalling API venv"
        sudo -u relay "$APP_DIR/api/.venv/bin/pip" install --quiet -e "$APP_DIR/api"
        # Bridge inherits relay-api editable; re-install both for safety
        sudo -u relay "$APP_DIR/bridge/.venv/bin/pip" install --quiet -e "$APP_DIR/api" -e "$APP_DIR/bridge"
    fi
    if echo "$CHANGED" | grep -qE '^bridge/pyproject.toml$'; then
        echo "$(ts) bridge/pyproject.toml changed -- reinstalling bridge venv"
        sudo -u relay "$APP_DIR/bridge/.venv/bin/pip" install --quiet -e "$APP_DIR/api" -e "$APP_DIR/bridge"
    fi

    # --- 3. Update Node deps + rebuild UI --------------------------------
    if echo "$CHANGED" | grep -qE '^ui/(package(-lock)?\.json|next\.config\.mjs)$'; then
        echo "$(ts) ui deps or config changed -- npm install"
        cd "$APP_DIR/ui"
        sudo -u relay npm install --silent --no-audit --no-fund
        cd - >/dev/null
    fi
    if echo "$CHANGED" | grep -qE '^ui/'; then
        echo "$(ts) ui source changed -- rebuilding"
        cd "$APP_DIR/ui"
        sudo -u relay npm run build --silent
        cd - >/dev/null
    fi

    # --- 4. Alembic migrations ------------------------------------------
    if echo "$CHANGED" | grep -qE '^api/alembic/versions/'; then
        echo "$(ts) new migration(s) -- alembic upgrade head"
        sudo -u relay bash -c "set -a && source $ETC_DIR/secrets.env && set +a && cd $APP_DIR/api && .venv/bin/alembic upgrade head"
    fi

    # --- 5. systemd unit changes ----------------------------------------
    if echo "$CHANGED" | grep -qE '^deploy/relay-(api|bridge|ui)\.service$'; then
        echo "$(ts) systemd unit(s) changed -- reinstalling"
        install -m 644 "$APP_DIR/deploy/relay-api.service" /etc/systemd/system/
        install -m 644 "$APP_DIR/deploy/relay-bridge.service" /etc/systemd/system/
        install -m 644 "$APP_DIR/deploy/relay-ui.service" /etc/systemd/system/
        systemctl daemon-reload
    fi

    # --- 6. nginx config changes ----------------------------------------
    if echo "$CHANGED" | grep -qE '^deploy/nginx\.conf$'; then
        echo "$(ts) nginx.conf changed -- reinstalling + reloading"
        install -m 644 "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/relay
        nginx -t && systemctl reload nginx
    fi

    # --- 7. Restart services -------------------------------------------
    echo "$(ts) restarting services"
    systemctl restart relay-api relay-bridge relay-ui

    echo "$(ts) redeploy done"
} 2>&1 | tee -a "$LOG"
