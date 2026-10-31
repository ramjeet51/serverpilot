# ServerPilot

Management console for Ubuntu servers. Phase 1 runs the control plane on your Mac: Next.js, FastAPI, Celery, PostgreSQL, and Redis, supervised by PM2. The Ubuntu agent is Phase 2.

```
serverpilot/
├── frontend/          Next.js dashboard
├── backend/           FastAPI, Celery worker, agent gateway, Alembic
├── agent/             Agent environment template (installer arrives in Phase 2)
├── scripts/           setup, start, stop, restart, deploy, health, backup
├── ecosystem.config.js
└── docs/
```

## Run it

```bash
./scripts/setup.sh
./scripts/start.sh
./scripts/health-check.sh
```

Open http://127.0.0.1:3000 and sign in with `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD` from `backend/.env`. Change that password from Security after the first login.

| Command | What it does |
| --- | --- |
| `./scripts/stop.sh` | Stop the four PM2 apps. Add `--delete` to remove them from PM2. |
| `./scripts/restart.sh` | Restart every app, or one: `./scripts/restart.sh serverpilot-backend` |
| `./scripts/logs.sh` | Follow logs. Optional app name. |
| `./scripts/deploy.sh` | Install, migrate, rebuild, reload, then health-check. |
| `./scripts/backup.sh` | Gzip a PostgreSQL dump into `backups/`. |
| `pm2 save` | Already run by start/restart. |

PostgreSQL and Redis stay running as Homebrew services. They are not stopped with the apps.

## What Phase 1 can do

- Sign in, refresh, sign out, and change your password.
- Create platform accounts with admin, operator, or viewer roles.
- Queue a diagnostics job or a cancellable sleep test. The worker writes logs and the dashboard updates over WebSocket.
- Read the audit log.
- See PostgreSQL, Redis, the API, the worker, and the agent gateway on the dashboard.

Server management, files, packages, Docker, and deployments are later phases. Those screens are not in the UI until the endpoints exist.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
cd frontend && npm test
```

More detail is in `docs/`.
