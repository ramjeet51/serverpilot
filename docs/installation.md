# Installation

Follow `docs/macos-setup.md`, then:

```bash
./scripts/setup.sh
./scripts/start.sh
./scripts/health-check.sh
```

Sign in at http://127.0.0.1:3000. The email and password are `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` in `backend/.env`.

Development, without PM2:

```bash
# terminal 1
cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# terminal 2
cd backend && .venv/bin/python -m celery -A app.worker.celery_app worker --loglevel INFO
# terminal 3
cd backend && .venv/bin/python -m uvicorn app.gateway.main:app --host 127.0.0.1 --port 8001
# terminal 4
cd frontend && npm run dev
```

`npm run dev` does not read the production PM2 port settings unless you pass `-p`. The production path is `./scripts/start.sh`.
