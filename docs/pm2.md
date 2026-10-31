# PM2

`ecosystem.config.js` reads `.env`, `backend/.env`, and `frontend/.env`. Paths are resolved from the file location, so the project directory may contain spaces.

| App | Working directory | Command |
| --- | --- | --- |
| `serverpilot-backend` | `backend/` | `backend/.venv/bin/python -m uvicorn app.main:app` |
| `serverpilot-worker` | `backend/` | `python -m celery -A app.worker.celery_app worker --pool threads` |
| `serverpilot-agent-gateway` | `backend/` | `python -m uvicorn app.gateway.main:app` |
| `serverpilot-frontend` | `frontend/` | `next start` |

Uvicorn worker count comes from `BACKEND_WORKERS`. PM2 runs one backend process; Uvicorn supervises its own workers on a single port. Do not add a second backend app on the same port.

Logs: `logs/<app>.out.log` and `logs/<app>.err.log`, or `./scripts/logs.sh [app-name]`.

Restart policy: autorestart, 10 max restarts, 3s delay, 30s kill timeout.

```bash
./scripts/start.sh
./scripts/stop.sh
./scripts/restart.sh serverpilot-worker
./scripts/deploy.sh          # deps, backup, migrate, rebuild, reload, health-check
pm2 status
pm2 save
```

On macOS, persist across reboot with `pm2 startup` (launchd) and `pm2 save`. See `docs/macos-setup.md`.
