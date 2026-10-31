# Backup and recovery

```bash
./scripts/backup.sh
```

Writes `backups/<database>_<timestamp>.sql.gz` and keeps the newest `BACKUP_KEEP` files (default 14). `./scripts/deploy.sh` takes a backup before migrating.

Restore into an empty database:

```bash
gunzip -c backups/serverpilot_YYYYMMDD_HHMMSS.sql.gz | \
  PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U serverpilot -d serverpilot
```

Use the `psql` from `brew --prefix postgresql@17`. Stop the PM2 apps first so nothing writes during the restore: `./scripts/stop.sh`.

Redis holds sessions and the job queue, not the system of record. Losing Redis signs everyone out and drops queued jobs that had not been written to PostgreSQL. Job rows themselves are in PostgreSQL.

Copy `backups/` and the `.env` files when you move the control plane. `.env` files are the only copy of the generated secrets.
