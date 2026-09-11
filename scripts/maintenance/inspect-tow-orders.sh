#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -lt 1 ]]; then
    echo "Usage: $0 SHIP_ID [SHIP_ID ...]" >&2
    exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

docker compose exec -T backend \
    python -m app.scripts.tow_order_runtime_diagnostic "$@"
