#!/usr/bin/env bash
# Stop all ServerPilot PM2 applications (PostgreSQL and Redis keep running).
#   ./scripts/stop.sh            stop apps
#   ./scripts/stop.sh --delete   stop and remove them from the PM2 process list
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_cmd pm2 "Run ./scripts/setup.sh first"

if [[ "${1:-}" == "--delete" ]]; then
  pm2 delete "$PROJECT_ROOT/ecosystem.config.js" || true
else
  pm2 stop "$PROJECT_ROOT/ecosystem.config.js" || true
fi
pm2 save --force >/dev/null
pm2 status
