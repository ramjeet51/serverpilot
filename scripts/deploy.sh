#!/usr/bin/env bash
# Deploy an application update: dependencies, migrations, frontend build, zero-downtime PM2 reload, health check.
#   ./scripts/deploy.sh             deploy the current working tree
#   ./scripts/deploy.sh --pull      git pull --ff-only first
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_env

if [[ "${1:-}" == "--pull" ]]; then
  info "Pulling latest code"
  git -C "$PROJECT_ROOT" pull --ff-only
fi

info "Updating environment files with any new keys"
"$VENV_PY" "$PROJECT_ROOT/scripts/init_env.py"

info "Installing backend dependencies"
"$VENV_PY" -m pip install --quiet -r "$BACKEND_DIR/requirements.txt"

info "Backing up database before migration"
"$PROJECT_ROOT/scripts/backup.sh"

info "Migrating database"
(cd "$BACKEND_DIR" && "$VENV_PY" -m alembic upgrade head && "$VENV_PY" -m app.cli seed)

info "Building frontend"
(cd "$FRONTEND_DIR" && npm install --no-audit --no-fund && npm run build)

info "Reloading PM2 applications"
pm2 startOrReload "$PROJECT_ROOT/ecosystem.config.js" --update-env
pm2 save >/dev/null

sleep 5
"$PROJECT_ROOT/scripts/health-check.sh"
