#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -ne 1 || ! "$1" =~ ^[0-9]+$ ]]; then
    echo "usage: $0 <activity_id>" >&2
    exit 2
fi

ACTIVITY_ID="$1"

ACTIVITY_ID="$ACTIVITY_ID" docker compose exec -T backend python - <<'PY'
import json
import os

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_activity_observation import GameActivityObservation
from app.models.planets_account import PlanetsAccount
from app.services.game_activity import get_owned_game_activity

activity_id = int(os.environ["ACTIVITY_ID"])

with SessionLocal() as session:
    roots = list(
        session.execute(
            select(GameActivityObservation).where(
                GameActivityObservation.activity_id == activity_id
            )
        ).scalars().all()
    )

if not roots:
    raise SystemExit(f"activity {activity_id} not found")

pairs = sorted({
    (row.observer_planets_account_id, row.game_id)
    for row in roots
})

print(f"===== API SEMANTICS FOR THREAD {activity_id} =====")
for linked_account_id, game_id in pairs:
    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(PlanetsAccount.id == linked_account_id)
        ).scalar_one_or_none()
    if account is None:
        print(f"\nobserver {linked_account_id}: linked account missing")
        continue

    payload = get_owned_game_activity(
        user_id=account.user_id,
        linked_account_id=linked_account_id,
        game_id=game_id,
        limit=1000,
    )
    if payload is None:
        print(f"\nobserver {linked_account_id}: API ownership lookup failed")
        continue

    thread_items = [
        item for item in payload["items"]
        if item["activity_id"] == activity_id
        or item.get("parent_id") == activity_id
        or item.get("thread_root_id") == activity_id
    ]

    print(
        f"\nobserver {linked_account_id} "
        f"({account.planets_username}) game {game_id}: {len(thread_items)} item(s)"
    )
    for item in sorted(thread_items, key=lambda value: value["activity_id"]):
        print(json.dumps({
            "activity_id": item.get("activity_id"),
            "parent_id": item.get("parent_id"),
            "thread_root_id": item.get("thread_root_id"),
            "kind": item.get("kind"),
            "visibility_source": item.get("visibility_source"),
            "source_id": item.get("source_id"),
            "source_name": item.get("source_name"),
            "target_id": item.get("target_id"),
            "target_name": item.get("target_name"),
            "target_type": item.get("target_type"),
            "conversation_with_id": item.get("conversation_with_id"),
            "conversation_with_name": item.get("conversation_with_name"),
            "conversation_player_ids": item.get("conversation_player_ids"),
            "message": item.get("message"),
        }, ensure_ascii=False, sort_keys=True))
PY
