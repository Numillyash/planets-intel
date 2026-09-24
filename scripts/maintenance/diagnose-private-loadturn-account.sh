#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

printf '===== PRIVATE LOADTURN ACCOUNT DIAGNOSTIC =====\n'

set +e
docker compose exec -T backend python - \
    < scripts/maintenance/diagnose-private-loadturn-account.py
rc=$?
set -e

printf '\n===== RESULT =====\n'
printf 'diagnostic_rc=%d\n' "$rc"
exit "$rc"
