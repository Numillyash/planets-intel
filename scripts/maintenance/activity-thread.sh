#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -ne 1 || ! "$1" =~ ^[0-9]+$ ]]; then
  echo "Usage: $0 <activity_id>" >&2
  exit 2
fi

ROOT_ID="$1"

echo "===== ACTIVITY THREAD $ROOT_ID ====="

docker compose exec -T postgres sh -lc "
psql -X -v ON_ERROR_STOP=1 \
  -U \"\$POSTGRES_USER\" \
  -d \"\$POSTGRES_DB\" \
  -P pager=off \
  -v root_id='$ROOT_ID' <<'SQL'
SELECT
    observer_planets_account_id,
    game_id,
    activity_id,
    parent_id,
    turn,
    scope,
    visibility_source,
    outgoing_recipient_player_ids,
    source_id,
    source_name,
    target_id,
    target_name,
    target_type,
    message,
    raw_payload::jsonb ->> 'replycount' AS raw_replycount,
    CASE
        WHEN jsonb_typeof(raw_payload::jsonb -> '_replies') = 'array'
        THEN jsonb_array_length(raw_payload::jsonb -> '_replies')
        ELSE NULL
    END AS raw_replies_count,
    jsonb_pretty(raw_payload::jsonb -> '_replies') AS raw_replies
FROM game_activity_observations
WHERE activity_id = :root_id
   OR parent_id = :root_id
ORDER BY observer_planets_account_id, parent_id NULLS FIRST, activity_id;

SELECT
    observer_planets_account_id,
    activity_id,
    parent_id,
    source_name,
    target_name,
    message,
    jsonb_pretty(raw_payload::jsonb) AS raw_payload
FROM game_activity_observations
WHERE parent_id = :root_id
ORDER BY observer_planets_account_id, activity_id;
SQL
"
