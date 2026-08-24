from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.game_activity_observation import GameActivityObservation
from app.models.game_player_slot import GamePlayerSlot
from app.models.planets_account import PlanetsAccount


_ACTIVITY_VISIBILITY_SOURCES = {
    "ingame_activity",
    "private_activity",
    "outgoing_private_write",
}


def _integer(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    return value if isinstance(value, str) else None


def _normalized_recipient_player_ids(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            continue
        if item not in result:
            result.append(item)
    return sorted(result)


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


def _strongest_visibility_source(
    previous_source: str | None,
    observed_source: str | None,
) -> str | None:
    if "outgoing_private_write" in {previous_source, observed_source}:
        return "outgoing_private_write"
    if "private_activity" in {previous_source, observed_source}:
        return "private_activity"
    return observed_source or previous_source


def persist_game_activity_observations(
    session: Session,
    *,
    observer_planets_account_id: int,
    game_id: int,
    activity: list[dict[str, Any]],
    visibility_source: str | None = None,
) -> dict[str, int]:
    """Upsert observer-visible Planets.nu activity with endpoint provenance.

    Proven private visibility and explicit outgoing recipient metadata are sticky:
    a later copy from the broad in-game feed must never downgrade facts already
    established by the private feed or by IntelBoard's own successful write.
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
            GameActivityObservation.outgoing_recipient_player_ids,
        ).where(
            GameActivityObservation.observer_planets_account_id
            == observer_planets_account_id,
            GameActivityObservation.game_id == game_id,
            GameActivityObservation.activity_id.in_(activity_ids),
        )
    ).all()
    existing = {
        int(activity_id): (source, recipients)
        for activity_id, source, recipients in existing_rows
    }
    existing_ids = set(existing)

    rows: list[dict[str, Any]] = []
    for raw in records:
        activity_id = _integer(raw, "id")
        if activity_id is None:
            continue
        previous_source, previous_recipients = existing.get(
            activity_id,
            (None, None),
        )
        rows.append(
            {
                "observer_planets_account_id": observer_planets_account_id,
                "game_id": game_id,
                "activity_id": activity_id,
                "activity_type": _integer(raw, "activitytype"),
                "scope": _integer(raw, "scope"),
                "visibility_source": _strongest_visibility_source(
                    previous_source,
                    visibility_source,
                ),
                "outgoing_recipient_player_ids": (
                    _normalized_recipient_player_ids(previous_recipients) or None
                ),
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
            "outgoing_recipient_player_ids": stmt.excluded.outgoing_recipient_player_ids,
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


def mark_outgoing_private_message(
    *,
    linked_account_id: int,
    game_id: int,
    activity_id: int,
    recipient_player_ids: list[int],
) -> bool:
    """Attach factual IntelBoard write provenance to one reconciled activity."""

    recipients = _normalized_recipient_player_ids(recipient_player_ids)
    if not recipients:
        return False

    with SessionLocal() as session:
        row = session.execute(
            select(GameActivityObservation).where(
                GameActivityObservation.observer_planets_account_id
                == linked_account_id,
                GameActivityObservation.game_id == game_id,
                GameActivityObservation.activity_id == activity_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        row.visibility_source = "outgoing_private_write"
        row.outgoing_recipient_player_ids = recipients
        session.commit()
    return True


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


def _conversation_player_ids(
    row: GameActivityObservation,
    root: GameActivityObservation,
) -> list[int]:
    root_ids = _normalized_recipient_player_ids(
        root.outgoing_recipient_player_ids,
    )
    if root_ids:
        return root_ids
    return _normalized_recipient_player_ids(
        row.outgoing_recipient_player_ids,
    )


def _is_private_message(
    row: GameActivityObservation,
    root: GameActivityObservation,
) -> bool:
    """Classify privacy from factual write/feed provenance before raw shape."""

    if row.activity_type != 1:
        return False
    return (
        row.visibility_source in {"private_activity", "outgoing_private_write"}
        or root.visibility_source in {"private_activity", "outgoing_private_write"}
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
            "conversation_player_ids": [],
        }
    if row.activity_type == 5:
        return {
            "kind": "diplomacy",
            "thread_root_id": None,
            "conversation_with_id": None,
            "conversation_with_name": None,
            "conversation_player_ids": [],
        }
    if row.activity_type != 1:
        return {
            "kind": "unclassified",
            "thread_root_id": None,
            "conversation_with_id": None,
            "conversation_with_name": None,
            "conversation_player_ids": [],
        }

    root = _root_for(row, rows_by_id)
    if _is_private_message(row, root):
        conversation_player_ids = _conversation_player_ids(row, root)
        if conversation_player_ids:
            partner_id = None
            partner_name = None
        else:
            partner_id, partner_name = _conversation_partner(
                root,
                observer_account_id,
            )
        return {
            "kind": "private_message",
            "thread_root_id": root.activity_id,
            "conversation_with_id": partner_id,
            "conversation_with_name": partner_name,
            "conversation_player_ids": conversation_player_ids,
        }

    return {
        "kind": "player_message",
        "thread_root_id": root.activity_id if root.activity_id != row.activity_id else None,
        "conversation_with_id": None,
        "conversation_with_name": None,
        "conversation_player_ids": [],
    }


def _display_name_matches_slot(display_name: str, slot: GamePlayerSlot) -> bool:
    """Match Planets.nu's `username (Race)` display token to one roster slot."""

    value = display_name.strip().casefold()
    username = slot.username.strip().casefold()
    if not value or not username:
        return False
    return value == username or (
        value.startswith(f"{username} (")
        and value.endswith(")")
    )


def _active_human_slot_for_identity(
    slots: list[GamePlayerSlot],
    *,
    account_id: int | None,
    username: str | None,
) -> GamePlayerSlot | None:
    """Resolve one current human slot from exact factual account/name identity."""

    eligible = [slot for slot in slots if slot.status == 1 and slot.race_id < 100]
    if account_id not in (None, 0):
        matches = [slot for slot in eligible if slot.account_id == account_id]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None

    normalized_name = username.strip() if username else ""
    if not normalized_name:
        return None
    matches = [
        slot
        for slot in eligible
        if _display_name_matches_slot(normalized_name, slot)
    ]
    return matches[0] if len(matches) == 1 else None


def _private_group_player_ids_from_root(
    root: GameActivityObservation,
    *,
    slots: list[GamePlayerSlot],
    observer_account_id: int | None,
) -> list[int]:
    """Derive a factual group recipient set from Planets.nu targettype=4.

    Runtime-captured private activity uses targettype=4 and a comma-separated
    targetname containing every recipient display name.  The source is stored
    separately.  Resolve every participant against the current canonical roster,
    exclude the authenticated observer, and fail closed if any target token or
    the source cannot be mapped uniquely.
    """

    if root.target_type != 4 or not root.target_name:
        return []
    if observer_account_id in (None, 0):
        return []

    eligible = [slot for slot in slots if slot.status == 1 and slot.race_id < 100]
    source_slot = _active_human_slot_for_identity(
        eligible,
        account_id=root.source_id,
        username=root.source_name,
    )
    if source_slot is None:
        return []

    target_tokens = [token.strip() for token in root.target_name.split(",")]
    if not target_tokens or any(not token for token in target_tokens):
        return []

    target_slots: list[GamePlayerSlot] = []
    for token in target_tokens:
        matches = [
            slot
            for slot in eligible
            if _display_name_matches_slot(token, slot)
        ]
        if len(matches) != 1:
            return []
        target_slots.append(matches[0])

    participants: dict[int, GamePlayerSlot] = {source_slot.slot_id: source_slot}
    for slot in target_slots:
        participants[slot.slot_id] = slot

    observers = [
        slot
        for slot in participants.values()
        if slot.account_id == observer_account_id
    ]
    if len(observers) != 1:
        return []
    observer_slot_id = observers[0].slot_id

    return sorted(
        slot_id
        for slot_id in participants
        if slot_id != observer_slot_id
    )


def _legacy_private_partner_from_root(
    root: GameActivityObservation,
    *,
    slots: list[GamePlayerSlot],
    observer_account_id: int | None,
) -> tuple[int | None, str | None]:
    """Derive a direct legacy partner only when the observer is explicit.

    A private-activity root can target the game even when the rendered Planets.nu
    conversation contains multiple recipients.  Source-only identity therefore
    does not prove a one-to-one thread.  Resolve a single partner only when the
    root explicitly identifies the observer as source or target; otherwise fail
    closed until a factual recipient set is available.
    """

    source_slot = _active_human_slot_for_identity(
        slots,
        account_id=root.source_id,
        username=root.source_name,
    )
    target_slot = _active_human_slot_for_identity(
        slots,
        account_id=root.target_id,
        username=root.target_name,
    )

    def is_observer(slot: GamePlayerSlot | None) -> bool:
        return (
            slot is not None
            and observer_account_id not in (None, 0)
            and slot.account_id == observer_account_id
        )

    candidate: GamePlayerSlot | None = None
    if is_observer(source_slot):
        if target_slot is not None and not is_observer(target_slot):
            candidate = target_slot
    elif is_observer(target_slot):
        if source_slot is not None and not is_observer(source_slot):
            candidate = source_slot

    if candidate is None or is_observer(candidate):
        return None, None
    account_id = candidate.account_id
    return (
        account_id if account_id not in (None, 0) else None,
        candidate.username.strip() or None,
    )


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
        slots = list(
            session.execute(
                select(GamePlayerSlot).where(GamePlayerSlot.game_id == game_id)
            ).scalars().all()
        )

        rows_by_id = {row.activity_id: row for row in rows}
        slots_by_id = {slot.slot_id: slot for slot in slots}
        observer_account_id = owned_account.planets_account_id
        items = []
        for row in rows:
            semantics = _activity_semantics(
                row,
                rows_by_id=rows_by_id,
                observer_account_id=observer_account_id,
            )
            conversation_player_ids = list(
                semantics.get("conversation_player_ids") or [],
            )
            if (
                not conversation_player_ids
                and semantics.get("kind") == "private_message"
            ):
                root = _root_for(row, rows_by_id)
                conversation_player_ids = _private_group_player_ids_from_root(
                    root,
                    slots=slots,
                    observer_account_id=observer_account_id,
                )
                if conversation_player_ids:
                    semantics["conversation_player_ids"] = conversation_player_ids
                    semantics["conversation_with_id"] = None
                    semantics["conversation_with_name"] = None

            if conversation_player_ids:
                conversation_slots = [
                    slots_by_id[slot_id]
                    for slot_id in conversation_player_ids
                    if slot_id in slots_by_id
                ]
                semantics["conversation_with_id"] = None
                if len(conversation_slots) == len(conversation_player_ids):
                    semantics["conversation_with_name"] = " + ".join(
                        slot.username for slot in conversation_slots
                    )
                    if len(conversation_slots) == 1:
                        account_id = conversation_slots[0].account_id
                        semantics["conversation_with_id"] = (
                            account_id if account_id and account_id > 0 else None
                        )
            elif (
                semantics.get("kind") == "private_message"
                and semantics.get("conversation_with_id") is None
                and semantics.get("conversation_with_name") is None
            ):
                root = _root_for(row, rows_by_id)
                partner_id, partner_name = _legacy_private_partner_from_root(
                    root,
                    slots=slots,
                    observer_account_id=observer_account_id,
                )
                semantics["conversation_with_id"] = partner_id
                semantics["conversation_with_name"] = partner_name

            items.append(
                {
                    "activity_id": row.activity_id,
                    "activity_type": row.activity_type,
                    "scope": row.scope,
                    "visibility_source": row.visibility_source,
                    "outgoing_recipient_player_ids": (
                        _normalized_recipient_player_ids(
                            row.outgoing_recipient_player_ids,
                        )
                        or None
                    ),
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
