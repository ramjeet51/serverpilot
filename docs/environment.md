# Environment variables

Every setting is an environment variable. `scripts/init_env.py` (called by `setup.sh`) creates `.env` files from the examples and replaces `change-me` with random values. Existing files are kept; new keys are appended.

| File | Who reads it |
| --- | --- |
| `.env` | Shell scripts, PM2, backend (shared host, ports, database, Redis, logging) |
| `backend/.env` | FastAPI, Celery, agent gateway. Secrets override the root file. |
| `frontend/.env` | Next.js. Only `NEXT_PUBLIC_*` is visible in the browser. |
| `agent/.env` | The Ubuntu agent, from Phase 2. |

Precedence for the backend: process environment, then `backend/.env`, then the root `.env`.

Never put secrets in `NEXT_PUBLIC_*`. Never commit a real `.env`.

`APP_ENV=production` refuses placeholder secrets, secrets shorter than 32 characters, and `APP_DEBUG=true`. `REQUIRE_MFA` must stay `false` until Phase 7.

After changing `NEXT_PUBLIC_*`, rebuild: `cd frontend && npm run build && ./scripts/restart.sh serverpilot-frontend`.

The examples in each `.env.example` document every variable.
