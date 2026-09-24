#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

TIMEOUT_SECONDS="${PLANETS_INTEL_TARGET_REFRESH_TIMEOUT_SECONDS:-120}"
GAME_ID="${1:-}"

printf '===== TARGETED PRIVATE REFRESH DIAGNOSTIC =====\n'
printf 'timeout_seconds=%s\n' "$TIMEOUT_SECONDS"
if [[ -n "$GAME_ID" ]]; then
    printf 'requested_game_id=%s\n' "$GAME_ID"
fi

args=(--timeout "$TIMEOUT_SECONDS")
if [[ -n "$GAME_ID" ]]; then
    args+=(--game-id "$GAME_ID")
fi

set +e
docker compose exec -T backend python - "${args[@]}"     < scripts/maintenance/diagnose-private-refresh-target.py
rc=$?
set -e

printf '\n===== RESULT =====\n'
printf 'diagnostic_rc=%d\n' "$rc"
exit "$rc"
