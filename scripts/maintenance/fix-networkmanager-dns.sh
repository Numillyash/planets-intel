#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

OLD_DNS="${OLD_DNS:-8.8.8.8}"
NEW_DNS="${NEW_DNS:-1.1.1.1 9.9.9.9}"
REGISTRY_HOST="${REGISTRY_HOST:-registry-1.docker.io}"
LOG_DIR="$ROOT_DIR/logs/maintenance"
mkdir -p "$LOG_DIR"
STAMP="$(date '+%Y%m%d-%H%M%S')"
ROLLBACK="$LOG_DIR/${STAMP}-dns-rollback.sh"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "This script must run as root." >&2
    exit 2
fi

if ! command -v nmcli >/dev/null 2>&1; then
    echo "nmcli is not available; refusing to modify resolver configuration." >&2
    exit 3
fi

cat >"$ROLLBACK" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
EOF
chmod 700 "$ROLLBACK"

printf '===== BEFORE =====\n'
echo '-- /etc/resolv.conf'
grep -E '^(nameserver|search|options)[[:space:]]' /etc/resolv.conf || true

echo
echo '-- active NetworkManager connections'
nmcli -t -f NAME,DEVICE connection show --active || true

changed=0
while IFS=: read -r connection device; do
    [[ -n "$connection" ]] || continue
    [[ -n "$device" && "$device" != "--" ]] || continue

    current_dns="$(nmcli -g ipv4.dns connection show "$connection" 2>/dev/null || true)"
    if [[ " $current_dns " != *" $OLD_DNS "* && "$current_dns" != *"$OLD_DNS"* ]]; then
        continue
    fi

    current_ignore="$(nmcli -g ipv4.ignore-auto-dns connection show "$connection" 2>/dev/null || true)"

    printf '\nChanging connection %s on %s\n' "$connection" "$device"
    printf '  old DNS: %s\n' "${current_dns:-<empty>}"
    printf '  new DNS: %s\n' "$NEW_DNS"

    printf 'nmcli connection modify %q ipv4.dns %q ipv4.ignore-auto-dns %q\n' \
        "$connection" "$current_dns" "${current_ignore:-no}" >>"$ROLLBACK"
    printf 'nmcli device reapply %q || true\n' "$device" >>"$ROLLBACK"

    nmcli connection modify "$connection" ipv4.dns "$NEW_DNS"
    nmcli device reapply "$device"
    changed=$((changed + 1))
done < <(nmcli -t -f NAME,DEVICE connection show --active)

if [[ "$changed" -eq 0 ]]; then
    echo
    echo "No active NetworkManager connection explicitly using $OLD_DNS was found."
    echo "Nothing changed."
    rm -f "$ROLLBACK"
    exit 4
fi

sleep 2

echo
echo '===== AFTER ====='
echo '-- /etc/resolv.conf'
grep -E '^(nameserver|search|options)[[:space:]]' /etc/resolv.conf || true

echo
echo '-- NetworkManager DNS'
while IFS=: read -r connection device; do
    [[ -n "$connection" ]] || continue
    dns="$(nmcli -g ipv4.dns connection show "$connection" 2>/dev/null || true)"
    [[ -n "$dns" ]] && printf '%s (%s): %s\n' "$connection" "$device" "$dns"
done < <(nmcli -t -f NAME,DEVICE connection show --active)

echo
echo '===== DNS CHECK ====='
if getent ahostsv4 "$REGISTRY_HOST" | head -n 4; then
    echo 'system resolver: OK'
else
    echo 'system resolver: FAIL' >&2
    echo "Rollback script: $ROLLBACK" >&2
    exit 5
fi

echo
echo '===== REGISTRY HTTPS CHECK ====='
set +e
registry_result="$(curl -sS -o /dev/null -w 'http=%{http_code} remote_ip=%{remote_ip} connect=%{time_connect}s total=%{time_total}s' --connect-timeout 8 --max-time 15 "https://${REGISTRY_HOST}/v2/" 2>&1)"
registry_rc=$?
set -e
printf '%s\n' "$registry_result"

if [[ "$registry_rc" -ne 0 ]]; then
    echo "Registry connectivity still fails (curl exit $registry_rc)." >&2
    echo "Rollback script: $ROLLBACK" >&2
    exit 6
fi

echo
echo 'DNS repair applied successfully.'
echo "Rollback script: $ROLLBACK"
echo 'Next: bash /opt/planets-intel/scripts/deploy/production.sh'
