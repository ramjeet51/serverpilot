#!/usr/bin/env bash
# Shared helpers for ServerPilot scripts. Source this file; do not execute it.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
AGENT_DIR="$PROJECT_ROOT/agent"
VENV_PY="$BACKEND_DIR/.venv/bin/python"
PM2_APPS=(serverpilot-backend serverpilot-worker serverpilot-agent-gateway serverpilot-frontend)

if [[ -t 1 ]]; then
  C_RESET=$'\e[0m'; C_GREEN=$'\e[32m'; C_RED=$'\e[31m'; C_YELLOW=$'\e[33m'; C_BLUE=$'\e[34m'; C_BOLD=$'\e[1m'
else
  C_RESET=""; C_GREEN=""; C_RED=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""
fi

info()    { printf '%s==>%s %s\n' "$C_BLUE$C_BOLD" "$C_RESET" "$*"; }
success() { printf '%s  ✔%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn()    { printf '%s  !%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
fail()    { printf '%s  ✘%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
die()     { fail "$*"; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "Required command '$1' not found. $2"; }

# Export variables from an env file without executing arbitrary code paths beyond simple assignments.
load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  source "$file"
  set +a
}

load_env() {
  load_env_file "$PROJECT_ROOT/.env"
  load_env_file "$BACKEND_DIR/.env"
  load_env_file "$FRONTEND_DIR/.env"
}

pg_bin() {
  local prefix
  for formula in postgresql@17 postgresql@16 postgresql@15 postgresql; do
    prefix="$(brew --prefix "$formula" 2>/dev/null || true)"
    if [[ -n "$prefix" && -x "$prefix/bin/psql" ]]; then
      echo "$prefix/bin"
      return 0
    fi
  done
  command -v psql >/dev/null 2>&1 && dirname "$(command -v psql)" && return 0
  return 1
}

log_dir() {
  local dir="${LOG_DIRECTORY:-logs}"
  [[ "$dir" = /* ]] || dir="$PROJECT_ROOT/$dir"
  echo "$dir"
}
