# macOS setup

Requirements: macOS, Homebrew, Node.js 20 or newer, Python 3.11–3.13, PM2.

```bash
brew install postgresql@17 redis
brew install python@3.12   # if you do not already have 3.11–3.13
npm install -g pm2
brew services start postgresql@17
brew services start redis
```

`./scripts/setup.sh` does the rest:

1. Copies `.env.example` files to `.env` and fills secrets.
2. Creates the `serverpilot` role and the `serverpilot` and `serverpilot_test` databases.
3. Creates `backend/.venv`, installs Python packages, runs Alembic, seeds roles and the first admin.
4. Installs and builds the frontend.

If PostgreSQL was initialized under a different superuser than your macOS username, set `PG_SUPERUSER` in the root `.env` to that role and re-run `./scripts/db-setup.sh`.

## Start after reboot

Homebrew already restarts PostgreSQL and Redis. For the apps:

```bash
pm2 startup
# run the sudo command PM2 prints
pm2 save
```

`pm2 save` is also run by `./scripts/start.sh`. After a reboot, `pm2 resurrect` restores the process list if startup was installed.

Do not put PostgreSQL or Redis behind Docker for this deployment.
