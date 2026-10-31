# Troubleshooting

`./scripts/health-check.sh` prints each component. Then:

| Symptom | What to check |
| --- | --- |
| `role "…" does not exist` during db-setup | Set `PG_SUPERUSER` in `.env` to an existing superuser and re-run `./scripts/db-setup.sh`. |
| API exits immediately | `./scripts/logs.sh serverpilot-backend`. Usual causes: bad `DATABASE_URL`, PostgreSQL stopped, or a placeholder secret with `APP_ENV=production`. |
| Worker offline | `brew services list` — Redis must be `started`. Then `./scripts/logs.sh serverpilot-worker`. |
| Frontend 500 or old API URL | `NEXT_PUBLIC_*` is fixed at build time. Rebuild and `./scripts/restart.sh serverpilot-frontend`. |
| Login says the email is invalid | Use a normal mailbox shape. `admin@serverpilot.local` is accepted. |
| Login says invalid credentials | Password is `INITIAL_ADMIN_PASSWORD` in `backend/.env` until you change it. |
| Account locked | Wait `ACCOUNT_LOCKOUT_MINUTES`, or clear `locked_until` and `failed_login_count` on the user row. |
| Port in use | Change `BACKEND_PORT`, `FRONTEND_PORT`, or `AGENT_GATEWAY_PORT` in `.env` and restart. |
| PM2 shows `errored` | `pm2 describe serverpilot-backend` and the log files under `logs/`. |

```bash
cd backend && .venv/bin/python -m app.cli check
pm2 status
brew services list
```
