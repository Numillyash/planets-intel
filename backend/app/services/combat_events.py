from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.planet_observation import PlanetObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.services.intel_access import accessible_intel_accounts


def get_combat_events(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
) -> dict[str, Any] | None:
    """Return observer-aware VCR events plus conservative post-host evidence.

    CombatObservation remains the factual VCR layer. Result statuses below are a
    read-time analytical projection derived from two independent forms of
    evidence: later VCRs at the same position and exact-turn post-host factual
    ship/planet observations. No inferred result is persisted back into facts.
    """

    if turn <= 0:
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
                PrivateObservationBatch.observer_planets_account_id.in_(
                    accessible_ids
                ),
                CombatObservation.battle_turn == turn,
            )
            .order_by(
                CombatObservation.vcr_id,
                PrivateObservationBatch.observed_at,
                PrivateObservationBatch.id,
            )
        ).all()

        ship_rows = session.execute(
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
                PrivateObservationBatch.turn == turn,
                PrivateObservationBatch.observer_planets_account_id.in_(
                    accessible_ids
                ),
            )
        ).all()

        planet_rows = session.execute(
            select(
                PlanetObservation,
                PrivateObservationBatch,
                PlanetsAccount,
            )
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == PlanetObservation.batch_id,
            )
            .join(
                PlanetsAccount,
                PlanetsAccount.id
                == PrivateObservationBatch.observer_planets_account_id,
            )
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.turn == turn,
                PrivateObservationBatch.observer_planets_account_id.in_(
                    accessible_ids
                ),
            )
        ).all()

    def source_payload(
        entries: list[tuple[PrivateObservationBatch, PlanetsAccount]],
    ) -> list[dict[str, Any]]:
        grouped: dict[int, dict[str, Any]] = {}
        for batch, account in entries:
            source = grouped.setdefault(
                account.id,
                {
                    "linked_account_id": account.id,
                    "planets_username": account.planets_username,
                    "batch_ids": [],
                },
            )
            source["batch_ids"].append(batch.id)

        result = list(grouped.values())
        for source in result:
            source["batch_ids"] = sorted(set(source["batch_ids"]))
        result.sort(key=lambda item: item["linked_account_id"])
        return result

    def effective_info_turn(info_turn: int | None, batch_turn: int) -> int:
        return info_turn if info_turn is not None and info_turn > 0 else batch_turn

    ship_post_host: dict[
        int,
        list[tuple[PrivateObservationBatch, PlanetsAccount]],
    ] = defaultdict(list)
    for ship, batch, account in ship_rows:
        if effective_info_turn(ship.info_turn, batch.turn) != turn:
            continue
        ship_post_host[ship.ship_id].append((batch, account))

    planet_post_host: dict[
        int,
        list[tuple[PlanetObservation, PrivateObservationBatch, PlanetsAccount]],
    ] = defaultdict(list)
    for planet, batch, account in planet_rows:
        if effective_info_turn(planet.info_turn, batch.turn) != turn:
            continue
        planet_post_host[planet.planet_id].append((planet, batch, account))

    def is_ship_side(combat: CombatObservation, side: str) -> bool:
        hull_id = combat.left_hull_id if side == "left" else combat.right_hull_id
        has_starbase = (
            combat.left_is_starbase
            if side == "left"
            else combat.right_is_starbase
        )
        object_id = (
            combat.left_object_id
            if side == "left"
            else combat.right_object_id
        )
        return (
            object_id is not None
            and hull_id is not None
            and hull_id > 0
            and has_starbase is not True
        )

    def ship_side_ids(combat: CombatObservation) -> set[int]:
        result: set[int] = set()
        if is_ship_side(combat, "left") and combat.left_object_id is not None:
            result.add(int(combat.left_object_id))
        if is_ship_side(combat, "right") and combat.right_object_id is not None:
            result.add(int(combat.right_object_id))
        return result

    event_by_key: dict[tuple[int, int], CombatObservation] = {}
    event_sources: dict[
        tuple[int, int],
        list[tuple[PrivateObservationBatch, PlanetsAccount]],
    ] = defaultdict(list)

    for combat, batch, account in combat_rows:
        key = (combat.battle_turn, combat.vcr_id)
        event_by_key[key] = combat
        event_sources[key].append((batch, account))

    events_by_position: dict[
        tuple[int | None, int | None],
        list[CombatObservation],
    ] = defaultdict(list)
    for combat in event_by_key.values():
        events_by_position[(combat.x, combat.y)].append(combat)

    sequence_status: dict[tuple[int, int], str] = {}
    sequence_meta: dict[int, tuple[int, int]] = {}

    for position_events in events_by_position.values():
        ordered = sorted(position_events, key=lambda item: item.vcr_id)
        ship_ids_by_event = [ship_side_ids(event) for event in ordered]

        for index, event in enumerate(ordered):
            sequence_meta[event.vcr_id] = (index + 1, len(ordered))
            current_ids = ship_ids_by_event[index]
            later_ids: set[int] = set()
            for later in ship_ids_by_event[index + 1 :]:
                later_ids.update(later)

            for ship_id in current_ids:
                if ship_id in later_ids:
                    status = "survived_to_later_combat"
                else:
                    opponents = current_ids - {ship_id}
                    status = (
                        "defeated"
                        if opponents.intersection(later_ids)
                        else "unknown"
                    )
                sequence_status[(event.vcr_id, ship_id)] = status

    def side_payload(combat: CombatObservation, side: str) -> dict[str, Any]:
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

        ship = is_ship_side(combat, side)
        sequence = (
            sequence_status.get((combat.vcr_id, int(object_id)), "unknown")
            if ship and object_id is not None
            else None
        )

        result_status = sequence or "unknown"
        result_basis = (
            "later_vcr_same_turn_same_position"
            if sequence is not None and sequence != "unknown"
            else None
        )
        result_sources: list[dict[str, Any]] = []
        post_host_owner_id: int | None = None

        if ship and object_id is not None:
            post_sources = ship_post_host.get(int(object_id), [])
            if post_sources:
                result_status = "survived_post_host"
                result_basis = "direct_post_host_ship_observation"
                result_sources = source_payload(post_sources)

        if not ship and object_id is not None:
            post_entries = planet_post_host.get(int(object_id), [])
            if post_entries:
                owners = {
                    planet.owner_id
                    for planet, _batch, _account in post_entries
                    if planet.owner_id is not None
                }
                if len(owners) == 1:
                    post_host_owner_id = next(iter(owners))
                    result_status = (
                        "planet_held_post_host"
                        if post_host_owner_id == owner_id
                        else "planet_owner_changed_post_host"
                    )
                    result_basis = "direct_post_host_planet_observation"
                    result_sources = source_payload(
                        [(batch, account) for _planet, batch, account in post_entries]
                    )

        return {
            "side": side,
            "object_kind": "ship" if ship else "planet",
            "object_id": object_id,
            "owner_id": owner_id,
            "name": name,
            "hull_id": hull_id if ship else None,
            "has_starbase": has_starbase if not ship else None,
            "sequence_status": sequence,
            "result_status": result_status,
            "result_basis": result_basis,
            "result_sources": result_sources,
            "post_host_owner_id": post_host_owner_id,
        }

    events: list[dict[str, Any]] = []
    for key, combat in event_by_key.items():
        sequence_index, sequence_count = sequence_meta.get(combat.vcr_id, (1, 1))
        events.append(
            {
                "vcr_id": combat.vcr_id,
                "turn": combat.battle_turn,
                "battle_type": combat.battle_type,
                "x": combat.x,
                "y": combat.y,
                "sequence_index": sequence_index,
                "sequence_count": sequence_count,
                "sources": source_payload(event_sources[key]),
                "sides": [
                    side_payload(combat, "left"),
                    side_payload(combat, "right"),
                ],
            }
        )

    events.sort(key=lambda event: event["vcr_id"])

    return {
        "game_id": game_id,
        "turn": turn,
        "events": events,
    }
