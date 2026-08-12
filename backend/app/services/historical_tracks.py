from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
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
    """Build factual ship tracks from stored scan and combat evidence.

    Scan points are keyed by the ship's own info_turn so a stale sighting
    repeated in later turn files does not look like new movement. VCR combat
    points are later host-phase evidence and therefore take precedence over a
    scan point for the same ship and turn. Unknown movement across observation
    gaps stays unknown; no path is inferred between non-consecutive turns.
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
        scan_rows = session.execute(
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

        combat_rows = session.execute(
            select(
                CombatObservation,
                PrivateObservationBatch,
                PlanetsAccount,
            )
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == CombatObservation.batch_id,
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
                CombatObservation.battle_turn <= through_turn,
                CombatObservation.x.is_not(None),
                CombatObservation.y.is_not(None),
            )
            .order_by(
                CombatObservation.battle_turn,
                CombatObservation.vcr_id,
                PrivateObservationBatch.observed_at,
                PrivateObservationBatch.id,
            )
        ).all()

    candidates: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    metadata_candidates: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for ship, batch, account in scan_rows:
        observation_turn = (
            ship.info_turn
            if ship.info_turn is not None and ship.info_turn > 0
            else batch.turn
        )
        if observation_turn <= 0 or observation_turn > through_turn:
            continue

        candidate = {
            "ship_id": ship.ship_id,
            "turn": observation_turn,
            "snapshot_turn": batch.turn,
            "x": ship.x,
            "y": ship.y,
            "linked_account_id": account.id,
            "observer_name": account.planets_username,
            "name": ship.name,
            "owner_id": ship.owner_id,
            "evidence": "scan",
            "combat_vcr_id": None,
            "phase_priority": 0,
            "sort_key": (
                0,
                batch.turn,
                batch.observed_at,
                batch.id,
            ),
        }
        candidates[(ship.ship_id, observation_turn)].append(candidate)
        metadata_candidates[ship.ship_id].append(candidate)

    def add_combat_side(
        combat: CombatObservation,
        batch: PrivateObservationBatch,
        account: PlanetsAccount,
        *,
        object_id: int | None,
        is_starbase: bool | None,
        owner_id: int | None,
        name: str | None,
    ) -> None:
        if object_id is None or is_starbase is True:
            return
        if combat.x is None or combat.y is None:
            return

        candidate = {
            "ship_id": object_id,
            "turn": combat.battle_turn,
            "snapshot_turn": batch.turn,
            "x": combat.x,
            "y": combat.y,
            "linked_account_id": account.id,
            "observer_name": account.planets_username,
            "name": name,
            "owner_id": owner_id,
            "evidence": "combat",
            "combat_vcr_id": combat.vcr_id,
            # Combat is later host-phase positional evidence than an ordinary
            # scan for the same turn, so prefer it when both are available.
            "phase_priority": 1,
            "sort_key": (
                1,
                batch.turn,
                batch.observed_at,
                batch.id,
                combat.vcr_id,
            ),
        }
        candidates[(object_id, combat.battle_turn)].append(candidate)
        metadata_candidates[object_id].append(candidate)

    for combat, batch, account in combat_rows:
        add_combat_side(
            combat,
            batch,
            account,
            object_id=combat.left_object_id,
            is_starbase=combat.left_is_starbase,
            owner_id=combat.left_owner_id,
            name=combat.left_name,
        )
        add_combat_side(
            combat,
            batch,
            account,
            object_id=combat.right_object_id,
            is_starbase=combat.right_is_starbase,
            owner_id=combat.right_owner_id,
            name=combat.right_name,
        )

    points_by_ship: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for (ship_id, observation_turn), entries in candidates.items():
        selected = max(entries, key=lambda entry: entry["sort_key"])
        source_ids = sorted({entry["linked_account_id"] for entry in entries})
        source_names = sorted({entry["observer_name"] for entry in entries})

        points_by_ship[ship_id].append(
            {
                "turn": observation_turn,
                "snapshot_turn": selected["snapshot_turn"],
                "x": selected["x"],
                "y": selected["y"],
                "linked_account_ids": source_ids,
                "observer_names": source_names,
                "evidence": selected["evidence"],
                "combat_vcr_id": selected["combat_vcr_id"],
            }
        )

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

        meta_entries = metadata_candidates.get(ship_id, [])
        latest_meta = max(
            meta_entries,
            key=lambda entry: (
                entry["turn"],
                entry["phase_priority"],
                entry["sort_key"],
            ),
        ) if meta_entries else None

        tracks.append(
            {
                "ship_id": ship_id,
                "name": latest_meta["name"] if latest_meta else None,
                "owner_id": latest_meta["owner_id"] if latest_meta else None,
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
