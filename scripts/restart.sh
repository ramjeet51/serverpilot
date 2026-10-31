#!/usr/bin/env bash
# Restart ServerPilot PM2 applications, re-reading environment files.
#   ./scripts/restart.sh                       all apps
#   ./scripts/restart.sh serverpilot-backend   a single app
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_cmd pm2 "Run ./scripts/setup.sh first"

if [[ $# -gt 0 ]]; then
  pm2 restart "$PROJECT_ROOT/ecosystem.config.js" --only "$1" --update-env
else
  pm2 restart "$PROJECT_ROOT/ecosystem.config.js" --update-env
fi
pm2 save >/dev/null
pm2 status
