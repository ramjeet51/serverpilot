#!/usr/bin/env bash
# Start (or reload) all ServerPilot PM2 applications and persist the process list.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_env
require_cmd pm2 "Run ./scripts/setup.sh first"

for svc in postgresql@17 redis; do
  if brew list "$svc" >/dev/null 2>&1 && ! brew services list | awk -v s="$svc" '$1==s && $2=="started"{f=1} END{exit !f}'; then
    info "Starting Homebrew service $svc"
    brew services start "$svc" >/dev/null
  fi
done

[[ -x "$VENV_PY" ]] || die "Backend virtualenv missing. Run ./scripts/setup.sh"
[[ -d "$FRONTEND_DIR/.next" ]] || die "Frontend not built. Run: (cd frontend && npm run build)"
mkdir -p "$(log_dir)"

info "Applying database migrations"
(cd "$BACKEND_DIR" && "$VENV_PY" -m alembic upgrade head)

info "Starting PM2 applications"
pm2 startOrReload "$PROJECT_ROOT/ecosystem.config.js" --update-env
pm2 save >/dev/null
pm2 status
echo
echo "Frontend: http://${FRONTEND_HOST:-127.0.0.1}:${FRONTEND_PORT:-3000}"
echo "API:      http://${BACKEND_HOST:-127.0.0.1}:${BACKEND_PORT:-8000}/api/docs"
echo "Run ./scripts/health-check.sh to verify every component."
