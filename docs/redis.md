# Redis

Phase 1 uses the Homebrew Redis service on `127.0.0.1:6379`. Leave `REDIS_PASSWORD` empty unless you have set `requirepass`.

Redis holds:

- the Celery broker and result backend
- refresh-token records (`sp:refresh:<jti>`), so logout and token rotation take effect immediately
- login and API rate-limit counters
- the `serverpilot:events` pub/sub channel for live job updates
- the gateway's connected-agent set (Phase 2)

Tests use database 15 and flush it. Do not point `REDIS_URL` at database 15 in `backend/.env`.

```bash
brew services start redis
redis-cli ping    # PONG
```
