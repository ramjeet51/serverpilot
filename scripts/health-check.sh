#!/usr/bin/env bash
# Verify every ServerPilot component. Exits non-zero if anything is unhealthy.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_env
set +e

failures=0
check() { if eval "$2" >/dev/null 2>&1; then success "$1"; else fail "$1"; failures=$((failures + 1)); fi; }

BACKEND_URL="http://${BACKEND_HOST:-127.0.0.1}:${BACKEND_PORT:-8000}"
FRONTEND_URL="http://${FRONTEND_HOST:-127.0.0.1}:${FRONTEND_PORT:-3000}"
GATEWAY_URL="http://${AGENT_GATEWAY_HOST:-127.0.0.1}:${AGENT_GATEWAY_PORT:-8001}"
PG_BIN="$(pg_bin)"

info "Infrastructure"
check "PostgreSQL accepting connections" "\"$PG_BIN/pg_isready\" -h \"${POSTGRES_HOST:-127.0.0.1}\" -p \"${POSTGRES_PORT:-5432}\""
redis_ping=(redis-cli -h "${REDIS_HOST:-127.0.0.1}" -p "${REDIS_PORT:-6379}")
[[ -n "${REDIS_PASSWORD:-}" ]] && redis_ping+=(-a "$REDIS_PASSWORD" --no-auth-warning)
if [[ "$("${redis_ping[@]}" ping 2>/dev/null)" == "PONG" ]]; then success "Redis responds to PING"; else fail "Redis responds to PING"; failures=$((failures + 1)); fi

if [[ -n "${AGENT_TUNNEL_SSH:-}" ]]; then
  PM2_APPS+=(serverpilot-agent-tunnel)
fi

info "PM2 processes"
pm2_json="$(pm2 jlist 2>/dev/null)"
for app in "${PM2_APPS[@]}"; do
  status="$(printf '%s' "$pm2_json" | node -e '
    let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{
      const p=JSON.parse(d||"[]").find(x=>x.name===process.argv[1]);
      process.stdout.write(p?p.pm2_env.status:"missing");})' "$app")"
  check "$app is online (status: $status)" "[[ '$status' == online ]]"
done

info "HTTP endpoints"
check "Backend liveness  $BACKEND_URL/api/v1/health/live" "curl -fsS --max-time 5 $BACKEND_URL/api/v1/health/live"
check "Agent gateway     $GATEWAY_URL/health" "curl -fsS --max-time 5 $GATEWAY_URL/health"
check "Frontend          $FRONTEND_URL/login" "curl -fsS --max-time 10 -o /dev/null $FRONTEND_URL/login"

info "Platform health report"
report="$(curl -sS --max-time 15 "$BACKEND_URL/api/v1/health")"
if [[ -n "$report" ]]; then
  printf '%s' "$report" | node -e '
    let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{
      const r=JSON.parse(d).data;
      for (const [k,v] of Object.entries(r.components)) {
        const extra=[v.version&&`v${v.version}`,v.migration&&`migration ${v.migration}`,v.workers&&v.workers.join(","),
                     v.latency_ms!==undefined&&`${v.latency_ms}ms`,v.error].filter(Boolean).join(" · ");
        console.log(`   ${v.status==="ok"?"✔":"✘"} ${k.padEnd(9)} ${extra}`);
      }
      console.log(`   overall: ${r.status}`);
      process.exit(r.status==="ok"?0:1);})'
  [[ $? -eq 0 ]] || failures=$((failures + 1))
else
  fail "Backend health endpoint unreachable"; failures=$((failures + 1))
fi

echo
if (( failures == 0 )); then success "All checks passed"; else fail "$failures check(s) failed"; exit 1; fi
