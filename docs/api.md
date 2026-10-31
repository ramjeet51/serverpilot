# API

Base path: `/api/v1`. Interactive docs: http://127.0.0.1:8000/api/docs (disable with `API_DOCS_ENABLED=false`).

Responses are `{ "success": true, "data": ..., "meta": ... }` or `{ "success": false, "error": { "code", "message", "details" }, "request_id" }`. Lists include `meta.page`, `page_size`, `total`, and `pages`.

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/health/live` | Public liveness |
| GET | `/health` | Public. PostgreSQL, Redis, worker, gateway. |
| POST | `/auth/login` | Public. Sets refresh and CSRF cookies. Returns an access token. |
| POST | `/auth/refresh` | Refresh cookie plus `X-CSRF-Token`. Rotates both. |
| POST | `/auth/logout` | Refresh cookie plus CSRF. Revokes the session. |
| GET | `/auth/me` | Bearer |
| POST | `/auth/change-password` | Bearer |
| GET/POST/PATCH | `/accounts` | `accounts:read` / `accounts:write` |
| GET | `/jobs`, `/jobs/stats`, `/jobs/types`, `/jobs/{id}`, `/jobs/{id}/logs` | `jobs:read` |
| POST | `/jobs`, `/jobs/{id}/retry` | `jobs:write` |
| POST | `/jobs/{id}/cancel` | `jobs:cancel` |
| GET | `/audit` | `audit:read` |
| GET | `/monitoring/summary` | `monitoring:read` |
| WS | `/ws/events` | First message: `{"type":"auth","token":"<access token>"}` |

Roles: `admin` (everything), `operator` (read plus jobs, servers, files, software, services, docker, deployments), `viewer` (read only, except accounts and audit).

Access tokens expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 15). The browser keeps the access token in memory and the refresh token in an HttpOnly `SameSite=Strict` cookie scoped to `/api/v1/auth`.
