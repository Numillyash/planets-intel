from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.host_event_observation import HostEventObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.intel_access import accessible_intel_accounts


def apply_structured_host_evidence(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = {account.id for account in accessible}
    if linked_account_id not in accessible_ids or not accessible_ids:
        return result

    with SessionLocal() as session:
        rows = list(
            session.execute(
                select(
                    HostEventObservation,
                    PrivateObservationBatch,
                    PlanetsAccount,
                )
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == HostEventObservation.batch_id,
                )
                .join(
                    PlanetsAccount,
                    PlanetsAccount.id
                    == PrivateObservationBatch.observer_planets_account_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                    HostEventObservation.turn == turn,
                    HostEventObservation.event_type == "planet_owner_change_by_ship",
                )
            ).all()
        )

    by_ship: dict[int, list[tuple[HostEventObservation, PrivateObservationBatch, PlanetsAccount]]] = defaultdict(list)
    by_planet: dict[int, list[tuple[HostEventObservation, PrivateObservationBatch, PlanetsAccount]]] = defaultdict(list)

    for event, batch, account in rows:
        if event.ship_id is not None:
            by_ship[int(event.ship_id)].append((event, batch, account))
        if event.planet_id is not None:
            by_planet[int(event.planet_id)].append((event, batch, account))

    def same_location(event: HostEventObservation, item: dict[str, Any]) -> bool:
        x = item.get("x")
        y = item.get("y")
        if event.x is not None and isinstance(x, int) and event.x != x:
            return False
        if event.y is not None and isinstance(y, int) and event.y != y:
            return False
        return True

    def sources(entries: list[tuple[HostEventObservation, PrivateObservationBatch, PlanetsAccount]]) -> list[dict[str, Any]]:
        grouped: dict[int, dict[str, Any]] = {}
        for _event, batch, account in entries:
            source = grouped.setdefault(
                account.id,
                {
                    "linked_account_id": account.id,
                    "planets_username": account.planets_username,
                    "batch_ids": [],
                },
            )
            source["batch_ids"].append(batch.id)
        values = list(grouped.values())
        for value in values:
            value["batch_ids"] = sorted(set(value["batch_ids"]))
        values.sort(key=lambda value: value["linked_account_id"])
        return values

    events = result.get("events")
    if not isinstance(events, list):
        return result

    for item in events:
        if not isinstance(item, dict):
            continue
        sides = item.get("sides")
        if not isinstance(sides, list):
            continue

        for side in sides:
            if not isinstance(side, dict):
                continue
            object_id = side.get("object_id")
            if not isinstance(object_id, int):
                continue

            if side.get("object_kind") == "ship":
                matches = [
                    entry
                    for entry in by_ship.get(object_id, [])
                    if same_location(entry[0], item)
                ]
                if matches:
                    side["result_status"] = "survived_post_host"
                    side["result_basis"] = "structured_planet_ownership_report"
                    side["result_sources"] = sources(matches)
            elif side.get("object_kind") == "planet":
                matches = [
                    entry
                    for entry in by_planet.get(object_id, [])
                    if same_location(entry[0], item)
                ]
                if matches:
                    side["result_status"] = "planet_owner_changed_post_host"
                    side["result_basis"] = "structured_planet_ownership_report"
                    side["result_sources"] = sources(matches)

    return result
