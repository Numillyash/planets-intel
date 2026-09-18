#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

# Stream the checked-out read-only diagnostic into the already-running backend
# container. This inspects current persisted state without rebuilding or
# redeploying production.
docker compose exec -T backend python - \
    < backend/app/scripts/movement_blocker_runtime_diagnostic.py
