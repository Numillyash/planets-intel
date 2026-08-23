from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.game_activity_observation import GameActivityObservation
from app.models.planets_account import PlanetsAccount


_ACTIVITY_VISIBILITY_SOURCES = {"ingame_activity", "private_activity"}


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
    visibility_source: str | None = None,
) -> dict[str, int]:
    """Upsert observer-visible Planets.nu activity with endpoint provenance.

    ``private_activity`` is sticky: once the dedicated private feed has exposed
    an activity id to this observer, a later copy from the broad in-game feed
    must never downgrade that factual visibility provenance.
    """

    if (
        visibility_source is not None
        and visibility_source not in _ACTIVITY_VISIBILITY_SOURCES
    ):
        raise ValueError(f"unsupported activity visibility source: {visibility_source}")

    records = flatten_activity_records(activity)
    if not records:
        return {"game_activity_seen": 0, "game_activity_inserted": 0}

    activity_ids = [
        activity_id
        for raw in records
        if (activity_id := _integer(raw, "id")) is not None
    ]
    existing_rows = session.execute(
        select(
            GameActivityObservation.activity_id,
            GameActivityObservation.visibility_source,
        ).where(
            GameActivityObservation.observer_planets_account_id
            == observer_planets_account_id,
            GameActivityObservation.game_id == game_id,
            GameActivityObservation.activity_id.in_(activity_ids),
        )
    ).all()
    existing_sources = {
        int(activity_id): source
        for activity_id, source in existing_rows
    }
    existing_ids = set(existing_sources)

    rows: list[dict[str, Any]] = []
    for raw in records:
        activity_id = _integer(raw, "id")
        if activity_id is None:
            continue
        previous_source = existing_sources.get(activity_id)
        effective_source = (
            "private_activity"
            if "private_activity" in {previous_source, visibility_source}
            else visibility_source or previous_source
        )
        rows.append(
            {
                "observer_planets_account_id": observer_planets_account_id,
                "game_id": game_id,
                "activity_id": activity_id,
                "activity_type": _integer(raw, "activitytype"),
                "scope": _integer(raw, "scope"),
                "visibility_source": effective_source,
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
            "visibility_source": stmt.excluded.visibility_source,
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


def _root_for(
    row: GameActivityObservation,
    rows_by_id: dict[int, GameActivityObservation],
) -> GameActivityObservation:
    current = row
    visited: set[int] = set()
    while current.parent_id not in (None, 0):
        parent_id = int(current.parent_id)
        if parent_id in visited:
            break
        visited.add(parent_id)
        parent = rows_by_id.get(parent_id)
        if parent is None:
            break
        current = parent
    return current


def _is_private_message(
    row: GameActivityObservation,
    root: GameActivityObservation,
) -> bool:
    """Classify privacy from factual feed provenance before raw shape.

    The dedicated ``account/privateactivity`` endpoint is authoritative evidence
    that the observer received the activity privately. This remains true for
    multi-recipient messages that do not expose one target id. ``scope == 3``
    is retained as a compatibility fallback for rows stored before endpoint
    provenance was persisted.
    """

    if row.activity_type != 1:
        return False
    return (
        row.visibility_source == "private_activity"
        or root.visibility_source == "private_activity"
        or row.scope == 3
        or root.scope == 3
    )


def _conversation_partner(
    root: GameActivityObservation,
    observer_account_id: int | None,
) -> tuple[int | None, str | None]:
    if observer_account_id is None:
        return None, None

    if root.source_id == observer_account_id:
        partner_id = (
            int(root.target_id)
            if root.target_id not in (None, 0)
            else None
        )
        partner_name = root.target_name.strip() if root.target_name else None
        return partner_id, partner_name or None

    if root.target_id == observer_account_id:
        partner_id = (
            int(root.source_id)
            if root.source_id not in (None, 0)
            else None
        )
        partner_name = root.source_name.strip() if root.source_name else None
        return partner_id, partner_name or None

    # Multi-recipient private roots may not expose one target account. The
    # message remains factually private, but there is no safe single partner to
    # invent for the UI.
    return None, None


def _activity_semantics(
    row: GameActivityObservation,
    *,
    rows_by_id: dict[int, GameActivityObservation],
    observer_account_id: int | None,
) -> dict[str, object | None]:
    if row.activity_type == 10:
        return {
            "kind": "system",
            "thread_root_id": None,
            "conversation_with_id": None,
            "conversation_with_name": None,
        }
    if row.activity_type == 5:
        return {
            "kind": "diplomacy",
            "thread_root_id": None,
            "conversation_with_id": None,
            "conversation_with_name": None,
        }
    if row.activity_type != 1:
        return {
            "kind": "unclassified",
            "thread_root_id": None,
            "conversation_with_id": None,
            "conversation_with_name": None,
        }

    root = _root_for(row, rows_by_id)
    if _is_private_message(row, root):
        partner_id, partner_name = _conversation_partner(root, observer_account_id)
        return {
            "kind": "private_message",
            "thread_root_id": root.activity_id,
            "conversation_with_id": partner_id,
            "conversation_with_name": partner_name,
        }

    return {
        "kind": "player_message",
        "thread_root_id": root.activity_id if root.activity_id != row.activity_id else None,
        "conversation_with_id": None,
        "conversation_with_name": None,
    }


def get_owned_game_activity(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    limit: int = 500,
) -> dict[str, object] | None:
    """Return activity for the owning dashboard user only."""

    with SessionLocal() as session:
        owned_account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if owned_account is None:
            return None

        rows = list(
            session.execute(
                select(GameActivityObservation)
                .where(
                    GameActivityObservation.observer_planets_account_id
                    == linked_account_id,
                    GameActivityObservation.game_id == game_id,
                )
                .order_by(
                    GameActivityObservation.order_id.desc().nullslast(),
                    GameActivityObservation.activity_id.desc(),
                )
                .limit(limit)
            ).scalars().all()
        )

        rows_by_id = {row.activity_id: row for row in rows}
        observer_account_id = owned_account.planets_account_id
        items = []
        for row in rows:
            semantics = _activity_semantics(
                row,
                rows_by_id=rows_by_id,
                observer_account_id=observer_account_id,
            )
            items.append(
                {
                    "activity_id": row.activity_id,
                    "activity_type": row.activity_type,
                    "scope": row.scope,
                    "visibility_source": row.visibility_source,
                    "turn": row.turn,
                    "parent_id": row.parent_id,
                    "source_id": row.source_id,
                    "source_name": row.source_name,
                    "source_type": row.source_type,
                    "target_id": row.target_id,
                    "target_name": row.target_name,
                    "target_type": row.target_type,
                    "message": row.message,
                    "date_added": row.date_added,
                    **semantics,
                }
            )

    return {
        "game_id": game_id,
        "linked_account_id": linked_account_id,
        "count": len(items),
        "items": items,
    }
