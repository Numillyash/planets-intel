#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

GAME_ID="${1:-}"
ACCOUNT_ID="${2:-}"

if [[ -z "$GAME_ID" ]]; then
    printf 'usage: %s GAME_ID [LINKED_ACCOUNT_ID]\n' "$0" >&2
    exit 2
fi

args=("$GAME_ID")
if [[ -n "$ACCOUNT_ID" ]]; then
    args+=(--account-id "$ACCOUNT_ID")
fi

set +e
docker compose exec -T backend python - "${args[@]}" \
    < scripts/maintenance/diagnose-account-game-discovery.py
rc=$?
set -e

printf '\n===== RESULT =====\n'
printf 'diagnostic_rc=%d\n' "$rc"
exit "$rc"
