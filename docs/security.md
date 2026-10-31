# Security model

Phase 1 covers the management server. Agent mutual TLS is specified and arrives with the agent in Phase 2. Until then the gateway binds to `127.0.0.1` and only answers `/health`.

- Passwords are SHA-256 pre-hashed and then bcrypt-hashed. The pre-hash keeps passwords longer than bcrypt's 72-byte limit meaningful.
- Access tokens are JWTs. Refresh tokens are random IDs stored in Redis and are single-use: a replay fails because the record is deleted on refresh.
- Refresh and logout require a double-submit CSRF token. The browser stores it in `sessionStorage` and sends `X-CSRF-Token`.
- Login is rate-limited per IP and email. Repeated bad passwords lock the account (`ACCOUNT_LOCKOUT_*`).
- Every API route is rate-limited per IP in Redis. If Redis is down the limiter fails open and logs a warning; authentication still requires the database.
- RBAC permissions are checked on each route. Viewers cannot create jobs or accounts.
- CORS allows only `CORS_ORIGINS`. WebSocket connections from other origins are closed.
- Audit rows record sign-in, sign-out, password changes, account changes, and job actions, including failures.
- Job types are an allowlist with Pydantic models (`extra=forbid`). Browser input is never interpolated into a shell command.
- File roots, upload size, and operation timeouts are configured now and enforced when file operations land in Phase 5.
- Secrets are references (`credentials_references`) pointing at an env var, keychain, or vault. The table does not store secret values.
- Bind `BACKEND_HOST`, `FRONTEND_HOST`, and `AGENT_GATEWAY_HOST` to localhost or a trusted LAN address. Do not publish PostgreSQL.

`APP_ENV=production` rejects placeholder `APP_SECRET_KEY` and `JWT_SECRET_KEY`.
