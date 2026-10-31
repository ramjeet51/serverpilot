#!/usr/bin/env bash
# One-time (and re-runnable) setup of the ServerPilot Management Server on macOS.
#   ./scripts/setup.sh            full setup
#   SKIP_FRONTEND_BUILD=1 ./scripts/setup.sh
#   PYTHON_BIN=/opt/homebrew/bin/python3.12 ./scripts/setup.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

info "Checking prerequisites"
[[ "$(uname -s)" == "Darwin" ]] || warn "This script targets macOS; continuing anyway"
require_cmd brew "Install Homebrew from https://brew.sh"
require_cmd node "Install Node.js 20+ (e.g. 'brew install node@20' or nvm)"
require_cmd npm "Install Node.js 20+"
node_major="$(node -p 'process.versions.node.split(".")[0]')"
(( node_major >= 20 )) || die "Node.js 20+ required (found $(node -v))"
if ! command -v pm2 >/dev/null 2>&1; then
  info "Installing PM2 globally"
  npm install -g pm2
fi
success "node $(node -v), pm2 $(pm2 -v)"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  for candidate in python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1; then PYTHON_BIN="$(command -v "$candidate")"; break; fi
  done
fi
[[ -n "${PYTHON_BIN:-}" ]] || die "Python 3.11-3.13 required. Install with: brew install python@3.12"
success "python $("$PYTHON_BIN" --version 2>&1 | awk '{print $2}') ($PYTHON_BIN)"

info "Ensuring PostgreSQL and Redis Homebrew services"
brew list postgresql@17 >/dev/null 2>&1 || brew list postgresql@16 >/dev/null 2>&1 || brew install postgresql@17
brew list redis >/dev/null 2>&1 || brew install redis
for svc in postgresql@17 redis; do
  if brew list "$svc" >/dev/null 2>&1; then brew services start "$svc" >/dev/null || true; fi
done
success "Homebrew services started"

info "Creating environment files"
"$PYTHON_BIN" "$PROJECT_ROOT/scripts/init_env.py"

load_env
mkdir -p "$(log_dir)"

info "Setting up PostgreSQL database"
"$PROJECT_ROOT/scripts/db-setup.sh"

info "Creating backend virtual environment"
if [[ ! -x "$VENV_PY" ]]; then
  "$PYTHON_BIN" -m venv "$BACKEND_DIR/.venv"
fi
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r "$BACKEND_DIR/requirements-dev.txt"
success "Backend dependencies installed"

info "Running database migrations and seed"
(cd "$BACKEND_DIR" && "$VENV_PY" -m alembic upgrade head && "$VENV_PY" -m app.cli seed)

info "Installing frontend dependencies"
(cd "$FRONTEND_DIR" && npm install --no-audit --no-fund)
if [[ "${SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
  info "Building frontend (production)"
  (cd "$FRONTEND_DIR" && npm run build)
fi

echo
success "Setup complete."
echo "  Start the platform:   ./scripts/start.sh"
echo "  Check health:         ./scripts/health-check.sh"
echo "  Admin login:          ${INITIAL_ADMIN_EMAIL:-see backend/.env}"
echo "  Admin password:       INITIAL_ADMIN_PASSWORD in backend/.env (change it after first login)"
