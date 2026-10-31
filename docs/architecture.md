# Architecture

ServerPilot is a control plane on your Mac and, from Phase 2, an agent on each Ubuntu server. The agent connects outbound. The Mac never needs an inbound SSH session for normal administration.

```
Browser  --HTTP/WS-->  Next.js :3000
                 \-->  FastAPI  :8000  --SQL-->  PostgreSQL :5432
                       FastAPI          --pub--> Redis :6379 <-- Celery worker
                       Agent gateway :8001  <-- outbound WS --  Ubuntu agent (Phase 2)
```

| Process | PM2 name | Role |
| --- | --- | --- |
| Next.js | `serverpilot-frontend` | Dashboard |
| Uvicorn | `serverpilot-backend` | REST, auth, WebSocket fan-out |
| Celery | `serverpilot-worker` | Job execution and retries |
| Uvicorn | `serverpilot-agent-gateway` | Agent health and, later, agent sessions |

PostgreSQL and Redis are Homebrew services, not PM2 apps and not Docker.

Jobs are an allowlist (`platform.diagnostics`, `platform.sleep_test` in Phase 1). The API rejects anything else before it reaches a worker. There is no endpoint that runs a shell command from the browser.

Real-time updates: the worker publishes `job.updated` and `job.log` on Redis. The API relays those messages to browsers that have authenticated a WebSocket with an access token. Tokens are sent in the first message, not in the URL.

The gateway is a separate process so agent connection churn (Phase 2) does not restart the browser API.
