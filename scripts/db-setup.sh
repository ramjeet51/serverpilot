#!/usr/bin/env bash
# Idempotently create the ServerPilot PostgreSQL role, application database and test database.
# Connects as the local Homebrew superuser (your macOS user) via the Unix socket.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_env

PG_BIN="$(pg_bin)" || die "psql not found. Install with: brew install postgresql@17"
: "${POSTGRES_DB:?POSTGRES_DB not set}" "${POSTGRES_USER:?POSTGRES_USER not set}" "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD not set}"
TEST_DB="${POSTGRES_DB}_test"

"$PG_BIN/pg_isready" -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" >/dev/null \
  || die "PostgreSQL is not accepting connections. Run: brew services start postgresql@17"

PG_SUPERUSER="${PG_SUPERUSER:-$USER}"
psql_admin() {
  "$PG_BIN/psql" -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" -U "$PG_SUPERUSER" -d postgres \
    -v ON_ERROR_STOP=1 -qtA "$@"
}
psql_admin -c "SELECT 1" >/dev/null 2>&1 \
  || die "Cannot connect as PostgreSQL superuser '$PG_SUPERUSER'. Set PG_SUPERUSER in .env to an existing superuser role."

# psql only interpolates :'var' in scripts read from stdin, which also keeps the password out of `ps`.
if [[ "$(psql_admin -c "SELECT 1 FROM pg_roles WHERE rolname = '${POSTGRES_USER}'")" == "1" ]]; then
  echo "ALTER ROLE \"${POSTGRES_USER}\" WITH LOGIN PASSWORD :'pw';" | psql_admin -v pw="$POSTGRES_PASSWORD" >/dev/null
  success "Role ${POSTGRES_USER} exists (password synced from .env)"
else
  echo "CREATE ROLE \"${POSTGRES_USER}\" WITH LOGIN PASSWORD :'pw';" | psql_admin -v pw="$POSTGRES_PASSWORD" >/dev/null
  success "Role ${POSTGRES_USER} created"
fi

for db in "$POSTGRES_DB" "$TEST_DB"; do
  if [[ "$(psql_admin -c "SELECT 1 FROM pg_database WHERE datname = '${db}'")" == "1" ]]; then
    success "Database ${db} exists"
  else
    psql_admin -c "CREATE DATABASE \"${db}\" OWNER \"${POSTGRES_USER}\" ENCODING 'UTF8'" >/dev/null
    success "Database ${db} created"
  fi
  psql_admin -c "GRANT ALL PRIVILEGES ON DATABASE \"${db}\" TO \"${POSTGRES_USER}\"" >/dev/null
done
