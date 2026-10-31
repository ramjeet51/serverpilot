#!/usr/bin/env bash
# Tail PM2 logs. Pass an app name to follow one process, or no args for all four.
#   ./scripts/logs.sh
#   ./scripts/logs.sh serverpilot-backend
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_cmd pm2 "Run ./scripts/setup.sh first"
if [[ $# -gt 0 ]]; then
  exec pm2 logs "$1"
else
  exec pm2 logs
fi
