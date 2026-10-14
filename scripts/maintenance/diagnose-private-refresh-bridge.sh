#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

API_TEST_URL="${PLANETS_INTEL_PROXY_TEST_URL:-https://api.planets.nu/time?version=1}"
REFRESH_TIMEOUT_SECONDS="${PLANETS_INTEL_REFRESH_TIMEOUT_SECONDS:-180}"
GAME_ID="${1:-}"

section() {
    printf '\n===== %s =====\n' "$1"
}

section "CURRENT PROXY CONFIG"
host_proxy="$(sed -n 's/^PLANETSNU_PROXY_URL=//p' .env 2>/dev/null | tail -1 || true)"
printf 'host .env PLANETSNU_PROXY_URL=%s\n' "${host_proxy:-<missing>}"

container_proxy="$(
    docker compose exec -T backend sh -lc         'printf "%s" "${PLANETSNU_PROXY_URL:-}"'         2>/dev/null || true
)"
printf 'backend PLANETSNU_PROXY_URL=%s\n' "${container_proxy:-<missing>}"

section "BACKEND"
docker compose ps backend || true
if curl -fsS --connect-timeout 5 --max-time 10     http://127.0.0.1:18080/api/health
then
    printf '\nbackend_health=OK\n'
else
    printf '\nbackend_health=FAILED\n'
fi

proxy="${container_proxy:-$host_proxy}"
if [[ -z "$proxy" ]]; then
    section "RESULT"
    echo "DIAGNOSIS=proxy_not_configured"
    echo "The backend has no PLANETSNU_PROXY_URL to test."
    exit 2
fi

section "PROXY TRANSPORT"
printf 'proxy=%s\n' "$proxy"
printf 'test_url=%s\n' "$API_TEST_URL"

proxy_output="$(mktemp)"
proxy_error="$(mktemp)"
trap 'rm -f "$proxy_output" "$proxy_error"' EXIT

set +e
curl -sS -v     --connect-timeout 8     --max-time 20     --proxy "$proxy"     "$API_TEST_URL"     -o "$proxy_output"     2>"$proxy_error"
proxy_rc=$?
set -e

cat "$proxy_error"
printf 'proxy_curl_rc=%d\n' "$proxy_rc"
if [[ -s "$proxy_output" ]]; then
    printf '%s\n' '--- response body ---'
    cat "$proxy_output"
    printf '\n'
fi

section "SCHEDULER HEALTH"
set +e
scheduler_health="$(
    curl -fsS --connect-timeout 5 --max-time 10         http://127.0.0.1:18080/api/health/private-refresh 2>/dev/null
)"
scheduler_health_rc=$?
set -e
if [[ "$scheduler_health_rc" -eq 0 ]]; then
    printf '%s\n' "$scheduler_health"
else
    printf 'scheduler_health=<unavailable on current runtime> rc=%d\n' "$scheduler_health_rc"
fi

section "RECENT PRIVATE REFRESH LOGS"
docker compose logs --since=30m backend 2>&1     | grep -Ei         'background private refresh|proxy|connecterror|readtimeout|loadturn|failed'     | tail -200 || true

if [[ "$proxy_rc" -ne 0 ]]; then
    section "RESULT"
    echo "DIAGNOSIS=proxy_transport_failed"
    printf 'proxy=%s\n' "$proxy"
    echo "Private refresh is expected to remain stale until the bridge endpoint is reachable."
    echo "Next diagnostic target: Windows/WSL bridge host."
    echo "Companion scripts:"
    echo "  scripts/maintenance/diagnose-wsl-proxy-bridge.sh"
    echo "  scripts/maintenance/diagnose-windows-proxy-bridge.ps1"
    exit 2
fi

section "TARGETED STALE PRIVATE REFRESH"
set +e
target_args=()
if [[ -n "$GAME_ID" ]]; then
    target_args+=("$GAME_ID")
fi
PLANETS_INTEL_TARGET_REFRESH_TIMEOUT_SECONDS="$REFRESH_TIMEOUT_SECONDS" \
    bash scripts/maintenance/diagnose-private-refresh-target.sh "${target_args[@]}"
refresh_rc=$?
set -e
printf 'refresh_rc=%d\n' "$refresh_rc"

section "RESULT"
if [[ "$refresh_rc" -eq 0 ]]; then
    echo "DIAGNOSIS=proxy_transport_ok_target_refresh_completed"
    exit 0
fi

echo "DIAGNOSIS=proxy_transport_ok_target_refresh_failed"
exit "$refresh_rc"
