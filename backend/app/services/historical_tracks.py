from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.services.intel_access import accessible_intel_accounts


def get_historical_ship_tracks(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    through_turn: int,
) -> dict[str, Any] | None:
    """Build factual ship tracks from stored observer-specific snapshots.

    A point is keyed by the ship's own info_turn rather than by the batch turn.
    This prevents a stale sighting repeated in later turn files from looking like
    a new position. Only batches retrieved for turns <= through_turn are used,
    so historical mode never leaks future observations backwards. The returned
    series is rendering data only; no path is inferred across observation gaps.
    """

    if through_turn <= 0:
        return None

    with SessionLocal() as session:
        primary = session.execute(
            select(PlanetsAccount).where(
                PlanetsAccount.id == linked_account_id,
                PlanetsAccount.user_id == user_id,
                PlanetsAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()

    if primary is None:
        return None

    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = {account.id for account in accessible}
    if linked_account_id not in accessible_ids or not accessible_ids:
        return None

    with SessionLocal() as session:
        rows = session.execute(
            select(
                ShipObservation,
                PrivateObservationBatch,
                PlanetsAccount,
            )
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == ShipObservation.batch_id,
            )
            .join(
                PlanetsAccount,
                PlanetsAccount.id
                == PrivateObservationBatch.observer_planets_account_id,
            )
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.turn <= through_turn,
                PrivateObservationBatch.observer_planets_account_id.in_(
                    accessible_ids
                ),
                ShipObservation.x.is_not(None),
                ShipObservation.y.is_not(None),
            )
            .order_by(
                ShipObservation.ship_id,
                PrivateObservationBatch.turn,
                PrivateObservationBatch.observed_at,
                PrivateObservationBatch.id,
            )
        ).all()

    grouped: dict[
        tuple[int, int],
        list[tuple[ShipObservation, PrivateObservationBatch, PlanetsAccount]],
    ] = defaultdict(list)

    for ship, batch, account in rows:
        observation_turn = (
            ship.info_turn
            if ship.info_turn is not None and ship.info_turn > 0
            else batch.turn
        )
        if observation_turn <= 0 or observation_turn > through_turn:
            continue
        grouped[(ship.ship_id, observation_turn)].append(
            (ship, batch, account)
        )

    points_by_ship: dict[int, list[dict[str, Any]]] = defaultdict(list)
    metadata: dict[int, dict[str, Any]] = {}

    for (ship_id, observation_turn), entries in grouped.items():
        # Prefer the latest snapshot available by the requested historical time.
        # When observers disagree for the same info turn, the newest retrieved
        # factual record is selected while all observer IDs remain in provenance.
        selected_ship, selected_batch, _ = max(
            entries,
            key=lambda entry: (
                entry[1].turn,
                entry[1].observed_at,
                entry[1].id,
            ),
        )

        source_ids = sorted({entry[2].id for entry in entries})
        source_names = sorted({entry[2].planets_username for entry in entries})

        points_by_ship[ship_id].append(
            {
                "turn": observation_turn,
                "snapshot_turn": selected_batch.turn,
                "x": selected_ship.x,
                "y": selected_ship.y,
                "linked_account_ids": source_ids,
                "observer_names": source_names,
            }
        )

        current_meta = metadata.get(ship_id)
        meta_key = (
            observation_turn,
            selected_batch.turn,
            selected_batch.observed_at,
            selected_batch.id,
        )
        if current_meta is None or meta_key > current_meta["_key"]:
            metadata[ship_id] = {
                "_key": meta_key,
                "name": selected_ship.name,
                "owner_id": selected_ship.owner_id,
            }

    tracks: list[dict[str, Any]] = []

    for ship_id in sorted(points_by_ship):
        raw_points = sorted(
            points_by_ship[ship_id],
            key=lambda item: item["turn"],
        )
        points: list[dict[str, Any]] = []
        previous_turn: int | None = None

        for point in raw_points:
            turn = int(point["turn"])
            points.append(
                {
                    **point,
                    "gap_from_previous": (
                        previous_turn is not None
                        and turn - previous_turn > 1
                    ),
                }
            )
            previous_turn = turn

        meta = metadata[ship_id]
        tracks.append(
            {
                "ship_id": ship_id,
                "name": meta["name"],
                "owner_id": meta["owner_id"],
                "first_turn": points[0]["turn"],
                "last_turn": points[-1]["turn"],
                "points": points,
            }
        )

    return {
        "game_id": game_id,
        "through_turn": through_turn,
        "tracks": tracks,
    }
