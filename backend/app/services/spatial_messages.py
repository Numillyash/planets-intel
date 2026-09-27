import hashlib
from collections import OrderedDict
from typing import Any, Iterable

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.models.private_message_observation import PrivateMessageObservation
from app.models.private_observation_batch import PrivateObservationBatch


def _message_visual_identity(item: PrivateMessageObservation) -> str:
    """Return a source-collection-independent identity for one message fact.

    Planets.nu can expose the same raw message through more than one collection.
    Presentation dedupe therefore ignores only source_collection while retaining
    every factual semantic field that could make two observations distinct.
    """

    source = "|".join(
        [
            str(item.message_id),
            str(item.message_type),
            str(item.message_turn),
            str(item.owner_id),
            str(item.target_id),
            item.headline or "",
            item.body or "",
            str(item.x),
            str(item.y),
        ]
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _collapse_spatial_messages(
    rows: Iterable[PrivateMessageObservation],
    *,
    batch_id: int,
    observed_at: Any,
) -> list[dict[str, Any]]:
    collapsed: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for item in rows:
        key = _message_visual_identity(item)
        existing = collapsed.get(key)
        if existing is not None:
            sources = existing["source_collections"]
            if item.source_collection not in sources:
                sources.append(item.source_collection)
                sources.sort()
            continue

        collapsed[key] = {
            "message_key": key,
            "message_id": item.message_id,
            "message_type": item.message_type,
            "message_turn": item.message_turn,
            "owner_id": item.owner_id,
            "target_id": item.target_id,
            "headline": item.headline,
            "body": item.body,
            "x": item.x,
            "y": item.y,
            "source_collections": [item.source_collection],
            "batch_id": batch_id,
            "observed_at": observed_at,
        }

    return list(collapsed.values())


def get_spatial_private_messages(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
) -> dict[str, Any] | None:
    """Return coordinate-bearing raw messages for one owned observer snapshot.

    This intentionally does not use dashboard intel sharing. Raw message text is
    observer-specific correspondence/evidence and must not be widened merely
    because entity intel is shared. The selected linked account must belong to
    the authenticated local user.
    """

    if turn <= 0:
        return None

    with SessionLocal() as session:
        account = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
            )
        ).scalar_one_or_none()
        if account is None:
            return None

        batch = session.execute(
            select(PrivateObservationBatch)
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id
                == linked_account_id,
                PrivateObservationBatch.turn == turn,
            )
            .order_by(
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if batch is None:
            return None

        rows = list(
            session.execute(
                select(PrivateMessageObservation)
                .where(
                    PrivateMessageObservation.batch_id == batch.id,
                    PrivateMessageObservation.x.is_not(None),
                    PrivateMessageObservation.y.is_not(None),
                    PrivateMessageObservation.message_turn == turn,
                )
                .order_by(
                    PrivateMessageObservation.message_id,
                    PrivateMessageObservation.id,
                )
            ).scalars().all()
        )

        messages = _collapse_spatial_messages(
            rows,
            batch_id=batch.id,
            observed_at=batch.observed_at,
        )

        return {
            "game_id": game_id,
            "turn": turn,
            "linked_account_id": account.id,
            "planets_username": account.planets_username,
            "scope": "selected_observer_private_messages",
            "count": len(messages),
            "messages": messages,
        }
