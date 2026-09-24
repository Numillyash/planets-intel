#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

PORT="${1:-18088}"
API_TEST_URL="${PLANETS_INTEL_PROXY_TEST_URL:-https://api.planets.nu/time?version=1}"

section() {
    printf '\n===== %s =====\n' "$1"
}

section "WSL NETWORK"
ip -4 addr || true
printf '\n'
ip route || true
printf '\n'
printf 'candidate_wsl_ipv4='
hostname -I 2>/dev/null | tr ' ' '\n'     | grep -E '^[0-9]+(\.[0-9]+){3}$'     | grep -v '^127\.'     | head -1 || true

section "TINYPROXY SERVICE"
if command -v systemctl >/dev/null 2>&1; then
    systemctl status tinyproxy --no-pager -l || true
elif command -v service >/dev/null 2>&1; then
    service tinyproxy status || true
else
    echo "No systemctl/service command available."
fi

section "LISTENER"
if command -v ss >/dev/null 2>&1; then
    ss -lntp | grep -E "[:.]$PORT[[:space:]]" || true
else
    echo "ss is unavailable."
fi

section "LOCAL PROXY TEST"
set +e
curl -sS -v     --connect-timeout 8     --max-time 20     --proxy "http://127.0.0.1:$PORT"     "$API_TEST_URL"     -o /tmp/planets-intel-wsl-proxy-test.out
rc=$?
set -e
printf 'local_proxy_curl_rc=%d\n' "$rc"
if [[ -s /tmp/planets-intel-wsl-proxy-test.out ]]; then
    cat /tmp/planets-intel-wsl-proxy-test.out
    printf '\n'
fi

section "RESULT"
if [[ "$rc" -eq 0 ]]; then
    echo "DIAGNOSIS=wsl_proxy_local_ok"
    echo "If production still gets connection refused, inspect the Windows ZeroTier/portproxy bridge."
    exit 0
fi

echo "DIAGNOSIS=wsl_proxy_local_failed"
echo "Fix/restart Tinyproxy or its listener before changing the Windows portproxy."
exit 2
