# PostgreSQL

Phase 1 uses the Homebrew `postgresql@17` service on `127.0.0.1:5432`.

`./scripts/db-setup.sh` creates:

- role `POSTGRES_USER` (default `serverpilot`) with the password in the root `.env`
- database `POSTGRES_DB` (default `serverpilot`)
- database `serverpilot_test` for pytest

It connects as `PG_SUPERUSER` (default: your macOS username).

Schema changes go through Alembic:

```bash
cd backend
.venv/bin/python -m alembic revision --autogenerate -m "describe the change"
.venv/bin/python -m alembic upgrade head
```

`./scripts/start.sh` and `./scripts/deploy.sh` run `upgrade head` before serving traffic.

Check connectivity:

```bash
cd backend && .venv/bin/python -m app.cli check
```

The application role is not a superuser. Credentials live in `.env`, which is gitignored.
