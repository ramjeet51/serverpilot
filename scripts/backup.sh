#!/usr/bin/env bash
# Create a compressed PostgreSQL backup in ./backups (keeps the newest BACKUP_KEEP files, default 14).
# Restore: gunzip -c backups/<file>.sql.gz | psql -h 127.0.0.1 -U serverpilot -d serverpilot
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_env

PG_BIN="$(pg_bin)" || die "pg_dump not found"
BACKUP_DIR="$PROJECT_ROOT/backups"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
file="$BACKUP_DIR/${POSTGRES_DB}_$(date +%Y%m%d_%H%M%S).sql.gz"

PGPASSWORD="$POSTGRES_PASSWORD" "$PG_BIN/pg_dump" -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner | gzip > "$file"
chmod 600 "$file"
success "Backup written: $file ($(du -h "$file" | cut -f1))"

keep="${BACKUP_KEEP:-14}"
ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +"$((keep + 1))" | while read -r old; do rm -f "$old"; done
