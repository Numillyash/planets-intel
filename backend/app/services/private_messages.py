import hashlib
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.private_message_observation import PrivateMessageObservation


def _integer(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if not isinstance(value, str):
        return None
    return value


def _message_key(source_collection: str, raw: dict[str, Any]) -> str:
    message_id = _integer(raw, "id")
    if message_id is not None:
        source = f"{source_collection}|id|{message_id}"
    else:
        source = "|".join(
            [
                source_collection,
                "raw",
                str(_integer(raw, "messagetype")),
                str(_integer(raw, "turn")),
                str(_integer(raw, "ownerid")),
                str(_integer(raw, "target")),
                _text(raw, "headline") or "",
                _text(raw, "body") or "",
                str(_integer(raw, "x")),
                str(_integer(raw, "y")),
            ]
        )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def persist_private_message_observations(
    session: Session,
    *,
    batch_id: int,
    messages: list[dict[str, Any]],
    mymessages: list[dict[str, Any]],
) -> int:
    """Persist raw message records exactly as observer-specific source facts.

    No public/private/chat/system classification is inferred here. That is a
    separate semantic layer and must not widen access to private correspondence.
    """

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for source_collection, records in (
        ("messages", messages),
        ("mymessages", mymessages),
    ):
        for raw in records:
            message_key = _message_key(source_collection, raw)
            identity = (source_collection, message_key)
            if identity in seen:
                continue
            seen.add(identity)

            rows.append(
                {
                    "batch_id": batch_id,
                    "source_collection": source_collection,
                    "message_key": message_key,
                    "message_id": _integer(raw, "id"),
                    "message_type": _integer(raw, "messagetype"),
                    "message_turn": _integer(raw, "turn"),
                    "owner_id": _integer(raw, "ownerid"),
                    "target_id": _integer(raw, "target"),
                    "headline": _text(raw, "headline"),
                    "body": _text(raw, "body"),
                    "x": _integer(raw, "x"),
                    "y": _integer(raw, "y"),
                }
            )

    if not rows:
        return 0

    stmt = (
        pg_insert(PrivateMessageObservation.__table__)
        .values(rows)
        .on_conflict_do_nothing(
            constraint="uq_private_message_observation_batch_source_key",
        )
        .returning(PrivateMessageObservation.id)
    )
    return len(session.execute(stmt).scalars().all())
