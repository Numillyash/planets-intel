from typing import Any

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.game_activity_observation import GameActivityObservation


def _integer(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    return value if isinstance(value, str) else None


def flatten_activity_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return activity records plus nested replies, deduplicated by activity id."""

    flattened: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    stack = list(reversed(records))

    while stack:
        raw = stack.pop()
        activity_id = _integer(raw, "id")
        if activity_id is None or activity_id <= 0 or activity_id in seen_ids:
            continue

        seen_ids.add(activity_id)
        flattened.append(raw)

        replies = raw.get("_replies")
        if isinstance(replies, list):
            for reply in reversed(replies):
                if isinstance(reply, dict):
                    stack.append(reply)

    return flattened


def persist_game_activity_observations(
    session: Session,
    *,
    observer_planets_account_id: int,
    game_id: int,
    activity: list[dict[str, Any]],
) -> dict[str, int]:
    """Upsert observer-visible Planets.nu activity without widening visibility.

    Numeric activity/scope values are intentionally stored raw. Until a real
    player-authored sample proves their semantics, the persistence layer does
    not infer public/private/system classifications.
    """

    records = flatten_activity_records(activity)
    if not records:
        return {"game_activity_seen": 0, "game_activity_inserted": 0}

    activity_ids = [
        activity_id
        for raw in records
        if (activity_id := _integer(raw, "id")) is not None
    ]
    existing_ids = set(
        session.execute(
            select(GameActivityObservation.activity_id).where(
                GameActivityObservation.observer_planets_account_id
                == observer_planets_account_id,
                GameActivityObservation.game_id == game_id,
                GameActivityObservation.activity_id.in_(activity_ids),
            )
        ).scalars().all()
    )

    rows: list[dict[str, Any]] = []
    for raw in records:
        activity_id = _integer(raw, "id")
        if activity_id is None:
            continue
        rows.append(
            {
                "observer_planets_account_id": observer_planets_account_id,
                "game_id": game_id,
                "activity_id": activity_id,
                "activity_type": _integer(raw, "activitytype"),
                "scope": _integer(raw, "scope"),
                "turn": _integer(raw, "turn"),
                "parent_id": _integer(raw, "parentid"),
                "source_id": _integer(raw, "sourceid"),
                "source_name": _text(raw, "sourcename"),
                "source_type": _integer(raw, "sourcetype"),
                "target_id": _integer(raw, "targetid"),
                "target_name": _text(raw, "targetname"),
                "target_type": _integer(raw, "targettype"),
                "order_id": _integer(raw, "orderid"),
                "message": _text(raw, "message"),
                "date_added": _text(raw, "dateadded"),
                "raw_payload": raw,
            }
        )

    if not rows:
        return {"game_activity_seen": 0, "game_activity_inserted": 0}

    stmt = pg_insert(GameActivityObservation.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_game_activity_observer_game_activity",
        set_={
            "activity_type": stmt.excluded.activity_type,
            "scope": stmt.excluded.scope,
            "turn": stmt.excluded.turn,
            "parent_id": stmt.excluded.parent_id,
            "source_id": stmt.excluded.source_id,
            "source_name": stmt.excluded.source_name,
            "source_type": stmt.excluded.source_type,
            "target_id": stmt.excluded.target_id,
            "target_name": stmt.excluded.target_name,
            "target_type": stmt.excluded.target_type,
            "order_id": stmt.excluded.order_id,
            "message": stmt.excluded.message,
            "date_added": stmt.excluded.date_added,
            "raw_payload": stmt.excluded.raw_payload,
            "observed_at": func.now(),
        },
    )
    session.execute(stmt)

    inserted = sum(
        1
        for row in rows
        if int(row["activity_id"]) not in existing_ids
    )
    return {
        "game_activity_seen": len(rows),
        "game_activity_inserted": inserted,
    }
