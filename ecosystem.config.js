/**
 * PM2 ecosystem for the ServerPilot Management Server (macOS, native processes).
 *
 *   pm2 start ecosystem.config.js        start all apps
 *   pm2 reload ecosystem.config.js       reload after deploy
 *   pm2 logs serverpilot-backend         tail one app
 *
 * Configuration comes from .env, backend/.env and frontend/.env; nothing is hardcoded here.
 * Paths are derived from this file's location so the project can live anywhere (including paths with spaces).
 */
const fs = require("fs");
const path = require("path");

const ROOT = __dirname;
const BACKEND = path.join(ROOT, "backend");
const FRONTEND = path.join(ROOT, "frontend");
const PYTHON = path.join(BACKEND, ".venv", "bin", "python");

function parseEnvFile(file) {
  if (!fs.existsSync(file)) return {};
  const env = {};
  for (const raw of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx < 1) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

const shared = parseEnvFile(path.join(ROOT, ".env"));
const backendEnv = { ...shared, ...parseEnvFile(path.join(BACKEND, ".env")) };
const frontendEnv = { ...shared, ...parseEnvFile(path.join(FRONTEND, ".env")) };

const get = (env, key, fallback) => (env[key] !== undefined && env[key] !== "" ? env[key] : fallback);
const logDirSetting = get(shared, "LOG_DIRECTORY", "logs");
const LOG_DIR = path.isAbsolute(logDirSetting) ? logDirSetting : path.join(ROOT, logDirSetting);

const common = {
  autorestart: true,
  max_restarts: 10,
  min_uptime: "10s",
  restart_delay: 3000,
  exp_backoff_restart_delay: 200,
  kill_timeout: 30000,
  merge_logs: true,
  time: true,
  log_date_format: "YYYY-MM-DD HH:mm:ss Z",
};

const logs = (name) => ({
  out_file: path.join(LOG_DIR, `${name}.out.log`),
  error_file: path.join(LOG_DIR, `${name}.err.log`),
});

// PM2 hands `script` to a shell. A project path with spaces ("New folder") must be quoted,
// so each app is `/bin/bash -c` with a quoted executable rather than the executable path itself.
function bashApp(name, cwd, command) {
  return {
    name,
    cwd,
    script: "/bin/bash",
    interpreter: "none",
    args: ["-c", command],
    exec_mode: "fork",
    instances: 1,
    ...common,
    ...logs(name.replace("serverpilot-", "")),
  };
}

const py = JSON.stringify(PYTHON);
const nextBin = JSON.stringify(path.join(FRONTEND, "node_modules", "next", "dist", "bin", "next"));

const pythonEnv = {
  ...backendEnv,
  PYTHONUNBUFFERED: "1",
  PYTHONDONTWRITEBYTECODE: "1",
  // Required for forking Celery/uvicorn workers on macOS (Objective-C runtime fork safety).
  OBJC_DISABLE_INITIALIZE_FORK_SAFETY: "YES",
};

const apps = [
    {
      ...bashApp(
        "serverpilot-backend",
        BACKEND,
        // One PM2 process; Uvicorn's own supervisor manages BACKEND_WORKERS processes on one socket.
        `exec ${py} -m uvicorn app.main:app --host ${get(backendEnv, "BACKEND_HOST", "127.0.0.1")} --port ${get(backendEnv, "BACKEND_PORT", "8000")} --workers ${get(backendEnv, "BACKEND_WORKERS", "1")} --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-server-header --no-access-log`,
      ),
      env: pythonEnv,
    },
    {
      ...bashApp(
        "serverpilot-worker",
        BACKEND,
        // threads: Celery's prefork pool crashes on macOS (fast_trace_task unpack error) before the job runs.
        `exec ${py} -m celery -A app.worker.celery_app worker --loglevel ${get(backendEnv, "LOG_LEVEL", "INFO")} --pool threads --concurrency ${get(backendEnv, "CELERY_CONCURRENCY", "2")} --queues serverpilot --hostname serverpilot-worker@%h --without-gossip --without-mingle`,
      ),
      env: pythonEnv,
    },
    {
      ...bashApp(
        "serverpilot-agent-gateway",
        BACKEND,
        `exec ${py} -m uvicorn app.gateway.main:app --host ${get(backendEnv, "AGENT_GATEWAY_HOST", "127.0.0.1")} --port ${get(backendEnv, "AGENT_GATEWAY_PORT", "8001")} --workers 1 --no-server-header --no-access-log`,
      ),
      env: pythonEnv,
    },
    {
      ...bashApp(
        "serverpilot-frontend",
        FRONTEND,
        `exec ${nextBin} start -H ${get(frontendEnv, "FRONTEND_HOST", "127.0.0.1")} -p ${get(frontendEnv, "FRONTEND_PORT", "3000")}`,
      ),
      env: { ...frontendEnv, NODE_ENV: "production" },
    },
];

// One-way networks: the Ubuntu host cannot dial this Mac, so the Mac keeps an SSH
// reverse tunnel and the agent dials 127.0.0.1 on that host.
const tunnelTarget = get(shared, "AGENT_TUNNEL_SSH", "");
const tunnelPort = get(shared, "AGENT_TUNNEL_REMOTE_PORT", "8001");
const localPort = get(backendEnv, "AGENT_GATEWAY_PORT", "8001");
if (/^[A-Za-z0-9._-]+@[A-Za-z0-9._:-]+$/.test(tunnelTarget) && /^\d{2,5}$/.test(tunnelPort) && /^\d{2,5}$/.test(localPort)) {
  apps.push(bashApp(
    "serverpilot-agent-tunnel",
    ROOT,
    `exec ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o BatchMode=yes -R 127.0.0.1:${tunnelPort}:127.0.0.1:${localPort} ${tunnelTarget}`,
  ));
}

module.exports = { apps };
