#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

REGISTRY_HOST="${REGISTRY_HOST:-registry-1.docker.io}"

echo "===== HOST RESOLVER ====="
if [[ -r /etc/resolv.conf ]]; then
    grep -E '^(nameserver|search|options)[[:space:]]' /etc/resolv.conf || true
else
    echo "/etc/resolv.conf unavailable"
fi

echo
if command -v nmcli >/dev/null 2>&1; then
    echo "===== NETWORKMANAGER DNS ====="
    nmcli -t -f GENERAL.CONNECTION,IP4.DNS,IP6.DNS device show 2>/dev/null || true
    echo
fi

if command -v resolvectl >/dev/null 2>&1; then
    echo "===== SYSTEMD-RESOLVED DNS ====="
    resolvectl status 2>/dev/null | sed -n '1,120p' || true
    echo
fi

if [[ -r /etc/docker/daemon.json ]]; then
    echo "===== /etc/docker/daemon.json ====="
    cat /etc/docker/daemon.json
    echo
fi

echo "===== SYSTEM RESOLUTION ====="
if getent ahostsv4 "$REGISTRY_HOST" >/tmp/planets-intel-registry-getent.$$ 2>&1; then
    head -n 4 /tmp/planets-intel-registry-getent.$$
    SYSTEM_DNS=OK
else
    cat /tmp/planets-intel-registry-getent.$$ || true
    SYSTEM_DNS=FAIL
fi
rm -f /tmp/planets-intel-registry-getent.$$
echo "system_dns=$SYSTEM_DNS"

echo
echo "===== HTTPS REGISTRY ====="
set +e
HTTP_RESULT="$(curl -sS -o /dev/null -w 'http=%{http_code} remote_ip=%{remote_ip} connect=%{time_connect}s total=%{time_total}s' --connect-timeout 8 --max-time 12 "https://${REGISTRY_HOST}/v2/" 2>&1)"
CURL_RC=$?
set -e
printf '%s\n' "$HTTP_RESULT"
echo "curl_exit=$CURL_RC"
echo "Note: HTTP 401 from Docker Registry is a successful connectivity test."

echo
echo "===== PUBLIC DNS PROBES ====="
probe_server() {
    local server="$1"
    if command -v dig >/dev/null 2>&1; then
        set +e
        local result
        result="$(dig +time=2 +tries=1 +short @"$server" "$REGISTRY_HOST" A 2>&1)"
        local rc=$?
        set -e
        if [[ $rc -eq 0 && -n "$result" ]]; then
            echo "$server: OK -> $(printf '%s\n' "$result" | paste -sd, -)"
        else
            echo "$server: FAIL${result:+ -> $result}"
        fi
        return
    fi

    if command -v nslookup >/dev/null 2>&1; then
        set +e
        local result
        result="$(nslookup "$REGISTRY_HOST" "$server" 2>&1)"
        local rc=$?
        set -e
        if [[ $rc -eq 0 ]]; then
            echo "$server: OK"
        else
            echo "$server: FAIL"
        fi
        return
    fi

    echo "$server: SKIP (dig/nslookup not installed)"
}

probe_server 8.8.8.8
probe_server 1.1.1.1
probe_server 9.9.9.9

echo
echo "===== LOCAL BASE IMAGES ====="
for image in node:20-alpine python:3.11-slim; do
    if docker image inspect "$image" >/dev/null 2>&1; then
        image_id="$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null || true)"
        echo "$image: PRESENT ${image_id}"
    else
        echo "$image: MISSING"
    fi
done

echo
echo "===== DOCKER ====="
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}' 2>/dev/null || docker version 2>/dev/null | head -n 20 || true

echo
echo "===== VERDICT HINT ====="
if [[ "$SYSTEM_DNS" == "FAIL" ]]; then
    echo "Host resolver cannot currently resolve ${REGISTRY_HOST}. Fix host/Docker DNS before rebuilding."
elif [[ $CURL_RC -ne 0 ]]; then
    echo "DNS resolved, but HTTPS connectivity to Docker Registry failed. Check routing/firewall/proxy."
else
    echo "Host DNS and registry HTTPS are reachable now. A deploy retry should be meaningful."
fi
