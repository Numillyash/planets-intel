#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

BRANCH="${DEPLOY_BRANCH:-feature/operational-ui}"
REMOTE="${DEPLOY_REMOTE:-origin}"
SERVICE="${DEPLOY_SERVICE:-backend}"
HEALTH_URL="${DEPLOY_HEALTH_URL:-http://127.0.0.1:18080/api/health}"
SELF_ARG="${1:-}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$ROOT_DIR/logs/deploy"
mkdir -p "$LOG_DIR"
LOG_FILE="${DEPLOY_LOG_FILE:-$LOG_DIR/$(date '+%Y%m%d-%H%M%S')-production.log}"
CURRENT_STEP="startup"

step() {
    CURRENT_STEP="$1"
    printf '\n==> %s\n' "$CURRENT_STEP"
    printf '\n===== %s =====\n' "$CURRENT_STEP" >>"$LOG_FILE"
}

run_logged() {
    printf '+ ' >>"$LOG_FILE"
    printf '%q ' "$@" >>"$LOG_FILE"
    printf '\n' >>"$LOG_FILE"
    "$@" >>"$LOG_FILE" 2>&1
}

fail() {
    local rc=$?
    printf '\nDEPLOY FAILED during: %s (exit %d)\n' "$CURRENT_STEP" "$rc" >&2
    printf 'Full log: %s\n' "$LOG_FILE" >&2
    printf '\n--- last 100 log lines ---\n' >&2
    tail -n 100 "$LOG_FILE" >&2 || true
    exit "$rc"
}
trap fail ERR

cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Not inside a Git repository: $ROOT_DIR" >&2
    exit 2
fi

# The first pass updates Git, then re-executes the newly pulled copy of this
# script. That prevents a deploy from continuing with stale deploy logic after
# the script itself changed upstream.
if [[ "$SELF_ARG" != "--after-update" ]]; then
    step "Preflight and Git update"

    tracked_dirty="$(git status --porcelain --untracked-files=no)"
    if [[ -n "$tracked_dirty" ]]; then
        echo "Refusing deploy: tracked working tree changes are present:" >&2
        printf '%s\n' "$tracked_dirty" >&2
        exit 3
    fi

    run_logged git fetch "$REMOTE" "$BRANCH"

    current_branch="$(git branch --show-current)"
    if [[ "$current_branch" != "$BRANCH" ]]; then
        run_logged git checkout "$BRANCH"
    fi

    run_logged git pull --ff-only "$REMOTE" "$BRANCH"

    local_head="$(git rev-parse HEAD)"
    remote_head="$(git rev-parse "$REMOTE/$BRANCH")"
    if [[ "$local_head" != "$remote_head" ]]; then
        echo "Refusing deploy: local HEAD does not match $REMOTE/$BRANCH" >&2
        echo "local:  $local_head" >&2
        echo "remote: $remote_head" >&2
        exit 4
    fi

    printf 'Updated to %s\n' "$local_head"
    printf 'Re-executing updated deploy script...\n'
    exec env DEPLOY_LOG_FILE="$LOG_FILE" \
        bash "$ROOT_DIR/scripts/deploy/production.sh" --after-update
fi

step "Git verification"
tracked_dirty="$(git status --porcelain --untracked-files=no)"
if [[ -n "$tracked_dirty" ]]; then
    echo "Refusing deploy: tracked working tree changes appeared after update:" >&2
    printf '%s\n' "$tracked_dirty" >&2
    exit 5
fi

HEAD_SHA="$(git rev-parse HEAD)"
ORIGIN_SHA="$(git rev-parse "$REMOTE/$BRANCH")"
if [[ "$HEAD_SHA" != "$ORIGIN_SHA" ]]; then
    echo "Refusing deploy: HEAD diverged after update" >&2
    exit 6
fi
printf 'HEAD: %s\n' "$HEAD_SHA"

step "Build production image"
run_logged docker compose build "$SERVICE"
printf 'Build: OK\n'

step "Backend test suite"
run_logged docker compose run --rm -T \
    -v "$ROOT_DIR/backend/tests:/app/tests:ro" \
    "$SERVICE" \
    python -m unittest discover \
    -s /app/tests \
    -p 'test_*.py'
printf 'Tests: OK\n'

test_summary="$(grep -E '^Ran [0-9]+ tests? in |^OK$' "$LOG_FILE" | tail -n 2 || true)"
if [[ -n "$test_summary" ]]; then
    printf '%s\n' "$test_summary"
fi

step "Database migration"
DB_BEFORE="$(docker compose run --rm -T "$SERVICE" alembic current 2>>"$LOG_FILE" | tee -a "$LOG_FILE" | tail -n 1)"
DB_HEAD="$(docker compose run --rm -T "$SERVICE" alembic heads 2>>"$LOG_FILE" | tee -a "$LOG_FILE" | tail -n 1)"
printf 'DB before: %s\n' "${DB_BEFORE:-unknown}"
printf 'DB target: %s\n' "${DB_HEAD:-unknown}"
run_logged docker compose run --rm -T "$SERVICE" alembic upgrade head
DB_AFTER="$(docker compose run --rm -T "$SERVICE" alembic current 2>>"$LOG_FILE" | tee -a "$LOG_FILE" | tail -n 1)"
printf 'DB after:  %s\n' "${DB_AFTER:-unknown}"

if [[ -n "$DB_HEAD" && "$DB_AFTER" != "$DB_HEAD" ]]; then
    echo "Migration did not reach Alembic head" >&2
    exit 7
fi

step "Recreate backend"
run_logged docker compose up -d --force-recreate "$SERVICE"
printf 'Backend recreate: OK\n'

step "Health check"
health_ok=0
for attempt in $(seq 1 30); do
    if health_body="$(curl -fsS "$HEALTH_URL" 2>>"$LOG_FILE")"; then
        printf '%s\n' "$health_body" >>"$LOG_FILE"
        health_ok=1
        break
    fi
    sleep 1
done
if [[ "$health_ok" -ne 1 ]]; then
    echo "Health endpoint did not become ready within 30 seconds" >&2
    exit 8
fi
printf 'Health: %s\n' "$health_body"

step "Final status"
run_logged docker compose ps
printf 'HEAD: %s\n' "$HEAD_SHA"
printf 'DB:   %s\n' "$DB_AFTER"
printf 'Log:  %s\n' "$LOG_FILE"
printf '\nDEPLOY OK\n'
