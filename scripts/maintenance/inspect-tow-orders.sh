#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -lt 1 ]]; then
    echo "Usage: $0 SHIP_ID [SHIP_ID ...]" >&2
    exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

# Feed the diagnostic from the checked-out host tree into the already-running
# backend container. This keeps the probe read-only and avoids rebuilding or
# redeploying production merely to inspect current persisted state.
docker compose exec -T backend python - "$@" \
    < backend/app/scripts/tow_order_runtime_diagnostic.py
