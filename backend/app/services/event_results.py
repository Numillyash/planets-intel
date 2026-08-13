from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.host_event_observation import HostEventObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.intel_access import accessible_intel_accounts


def _integer(record: dict[str, Any] | None, *keys: str) -> int | None:
    if record is None:
        return None
    for key in keys:
        value = record.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _catalog_by_id(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for record in records:
        item_id = _integer(record, "id")
        if item_id is not None:
            result[item_id] = record
    return result


def _component_name(record: dict[str, Any] | None) -> str | None:
    if record is None:
        return None
    value = record.get("name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _side_equipment(
    *,
    combat: CombatObservation,
    side_name: str,
    beams: dict[int, dict[str, Any]],
    torpedos: dict[int, dict[str, Any]],
) -> dict[str, Any] | None:
    payload = combat.payload if isinstance(combat.payload, dict) else {}
    raw_side = payload.get(side_name)
    if not isinstance(raw_side, dict):
        return None

    beam_id = _integer(raw_side, "beamid")
    torpedo_id = _integer(raw_side, "torpedoid")
    ammo = _integer(raw_side, "torpedos", "torpedoes", "ammo")

    torpedoes = (
        ammo
        if torpedo_id is not None and torpedo_id > 0
        else None
    )
    fighters = _integer(raw_side, "fighters")
    if fighters is None and (torpedo_id is None or torpedo_id <= 0):
        fighters = ammo

    equipment = {
        "beam_id": beam_id,
        "beam_name": _component_name(beams.get(beam_id)) if beam_id is not None else None,
        "beam_count": _integer(raw_side, "beamcount"),
        "torpedo_id": torpedo_id,
        "torpedo_name": _component_name(torpedos.get(torpedo_id)) if torpedo_id is not None else None,
        "launcher_count": _integer(raw_side, "launchercount"),
        "torpedoes": torpedoes,
        "fighters": fighters,
        "damage": _integer(raw_side, "damage"),
        "crew": _integer(raw_side, "crew"),
        "mass": _integer(raw_side, "mass"),
    }
    return equipment if any(value is not None for value in equipment.values()) else None


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

        combat_rows = list(
            session.execute(
                select(CombatObservation)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == CombatObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                    CombatObservation.battle_turn == turn,
                )
                .order_by(
                    CombatObservation.vcr_id,
                    PrivateObservationBatch.observed_at,
                    PrivateObservationBatch.id,
                )
            ).scalars().all()
        )

        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()

    by_ship: dict[
        int,
        list[tuple[HostEventObservation, PrivateObservationBatch, PlanetsAccount]],
    ] = defaultdict(list)
    by_planet: dict[
        int,
        list[tuple[HostEventObservation, PrivateObservationBatch, PlanetsAccount]],
    ] = defaultdict(list)

    for event, batch, account in rows:
        if event.ship_id is not None:
            by_ship[int(event.ship_id)].append((event, batch, account))
        if event.planet_id is not None:
            by_planet[int(event.planet_id)].append((event, batch, account))

    beams = _catalog_by_id(catalog.beams) if catalog is not None else {}
    torpedos = _catalog_by_id(catalog.torpedos) if catalog is not None else {}
    combat_by_vcr = {int(combat.vcr_id): combat for combat in combat_rows}

    def same_location(event: HostEventObservation, item: dict[str, Any]) -> bool:
        x = item.get("x")
        y = item.get("y")
        if event.x is not None and isinstance(x, int) and event.x != x:
            return False
        if event.y is not None and isinstance(y, int) and event.y != y:
            return False
        return True

    def sources(
        entries: list[
            tuple[HostEventObservation, PrivateObservationBatch, PlanetsAccount]
        ],
    ) -> list[dict[str, Any]]:
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

        vcr_id = item.get("vcr_id")
        combat = combat_by_vcr.get(vcr_id) if isinstance(vcr_id, int) else None

        for side in sides:
            if not isinstance(side, dict):
                continue
            object_id = side.get("object_id")
            if not isinstance(object_id, int):
                continue

            side_name = side.get("side")
            if (
                side.get("object_kind") == "ship"
                and combat is not None
                and side_name in {"left", "right"}
            ):
                side["combat_equipment"] = _side_equipment(
                    combat=combat,
                    side_name=side_name,
                    beams=beams,
                    torpedos=torpedos,
                )

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
