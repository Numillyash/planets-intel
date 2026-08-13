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
    """Build derived ship tracks from factual scan and VCR evidence.

    Scan points are keyed by the ship's own info_turn so a stale sighting
    repeated in later turn files does not look like new movement. VCR combat
    points are later host-phase positional evidence and therefore take
    precedence over a scan point for the same ship and turn.

    Combat sequence analysis is deliberately separate from stored facts. It is
    constrained to VCRs from the same turn *and the same coordinates*. A ship
    seen in a later VCR at that location demonstrably survived the earlier
    event. If its ship opponent continues and it does not, it is labelled
    defeated without claiming destroyed versus captured.
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
            "hull_id": ship.hull_id,
            "evidence": "scan",
            "combat_vcr_id": None,
            "combat_outcome": None,
            "combat_event": None,
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

    def is_ship_side(
        object_id: int | None,
        hull_id: int | None,
        has_starbase: bool | None,
    ) -> bool:
        return (
            object_id is not None
            and hull_id is not None
            and hull_id > 0
            and has_starbase is not True
        )

    def ship_side_ids(combat: CombatObservation) -> set[int]:
        result: set[int] = set()
        if is_ship_side(
            combat.left_object_id,
            combat.left_hull_id,
            combat.left_is_starbase,
        ):
            result.add(int(combat.left_object_id))
        if is_ship_side(
            combat.right_object_id,
            combat.right_hull_id,
            combat.right_is_starbase,
        ):
            result.add(int(combat.right_object_id))
        return result

    # Collapse copies of the same factual VCR returned through several
    # observers. The latest stored copy supplies the structural fields; source
    # provenance remains on the candidate entries below.
    event_by_key: dict[tuple[int, int], CombatObservation] = {}
    for combat, _batch, _account in combat_rows:
        event_by_key[(combat.battle_turn, combat.vcr_id)] = combat

    events_by_location: dict[
        tuple[int, int | None, int | None],
        list[CombatObservation],
    ] = defaultdict(list)
    for combat in event_by_key.values():
        events_by_location[
            (combat.battle_turn, combat.x, combat.y)
        ].append(combat)

    combat_outcomes: dict[tuple[int, int, int], str] = {}
    sequence_meta: dict[tuple[int, int], tuple[int, int]] = {}

    for (_battle_turn, _x, _y), location_events in events_by_location.items():
        ordered = sorted(location_events, key=lambda item: item.vcr_id)
        ship_ids_by_event = [ship_side_ids(event) for event in ordered]

        for index, event in enumerate(ordered):
            sequence_meta[(event.battle_turn, event.vcr_id)] = (
                index + 1,
                len(ordered),
            )
            current_ids = ship_ids_by_event[index]
            later_ids: set[int] = set()
            for ids in ship_ids_by_event[index + 1 :]:
                later_ids.update(ids)

            for ship_id in current_ids:
                if ship_id in later_ids:
                    outcome = "survived_to_later_combat"
                else:
                    opponents = current_ids - {ship_id}
                    outcome = (
                        "defeated"
                        if opponents.intersection(later_ids)
                        else "unknown"
                    )

                combat_outcomes[(event.battle_turn, event.vcr_id, ship_id)] = (
                    outcome
                )

    def side_fact(
        combat: CombatObservation,
        *,
        side: str,
    ) -> dict[str, Any]:
        if side == "left":
            object_id = combat.left_object_id
            owner_id = combat.left_owner_id
            hull_id = combat.left_hull_id
            name = combat.left_name
            has_starbase = combat.left_is_starbase
        else:
            object_id = combat.right_object_id
            owner_id = combat.right_owner_id
            hull_id = combat.right_hull_id
            name = combat.right_name
            has_starbase = combat.right_is_starbase

        ship = is_ship_side(object_id, hull_id, has_starbase)
        sequence_status = (
            combat_outcomes.get(
                (combat.battle_turn, combat.vcr_id, int(object_id)),
                "unknown",
            )
            if ship and object_id is not None
            else None
        )

        return {
            "side": side,
            "object_kind": "ship" if ship else "planet",
            "object_id": object_id,
            "owner_id": owner_id,
            "name": name,
            "hull_id": hull_id if ship else None,
            "has_starbase": has_starbase if not ship else None,
            "sequence_status": sequence_status,
        }

    combat_event_meta: dict[tuple[int, int], dict[str, Any]] = {}
    for event_key, combat in event_by_key.items():
        sequence_index, sequence_count = sequence_meta.get(event_key, (1, 1))
        combat_event_meta[event_key] = {
            "vcr_id": combat.vcr_id,
            "turn": combat.battle_turn,
            "battle_type": combat.battle_type,
            "x": combat.x,
            "y": combat.y,
            "sequence_index": sequence_index,
            "sequence_count": sequence_count,
            "analysis_basis": "later_vcr_same_turn_same_position",
            "sides": [
                side_fact(combat, side="left"),
                side_fact(combat, side="right"),
            ],
        }

    def add_combat_side(
        combat: CombatObservation,
        batch: PrivateObservationBatch,
        account: PlanetsAccount,
        *,
        object_id: int | None,
        has_starbase: bool | None,
        hull_id: int | None,
        owner_id: int | None,
        name: str | None,
    ) -> None:
        if not is_ship_side(object_id, hull_id, has_starbase):
            return
        if object_id is None or combat.x is None or combat.y is None:
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
            "hull_id": hull_id,
            "evidence": "combat",
            "combat_vcr_id": combat.vcr_id,
            "combat_outcome": combat_outcomes.get(
                (combat.battle_turn, combat.vcr_id, object_id),
                "unknown",
            ),
            "combat_event": combat_event_meta.get(
                (combat.battle_turn, combat.vcr_id)
            ),
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
            has_starbase=combat.left_is_starbase,
            hull_id=combat.left_hull_id,
            owner_id=combat.left_owner_id,
            name=combat.left_name,
        )
        add_combat_side(
            combat,
            batch,
            account,
            object_id=combat.right_object_id,
            has_starbase=combat.right_is_starbase,
            hull_id=combat.right_hull_id,
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
                "combat_outcome": selected["combat_outcome"],
                "combat_event": selected["combat_event"],
                "has_direct_scan": any(
                    entry["evidence"] == "scan"
                    for entry in entries
                ),
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
                "hull_id": latest_meta["hull_id"] if latest_meta else None,
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
