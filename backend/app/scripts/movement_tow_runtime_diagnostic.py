from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.services.movement_prediction import GRAVITONIC_HULL_NAMES
from app.services.movement_tow import (
    TowAttempt,
    TowShipState,
    hull_engine_count,
    payload_integer,
    payload_is_tow_mission,
    payload_tow_target_id,
    resolve_strict_tow_locks,
)


SAMPLE_LIMIT = 40


def _latest_factual_groups() -> list[tuple[int, int, int, int, int]]:
    with SessionLocal() as session:
        rows = list(
            session.execute(
                select(PrivateObservationBatch)
                .join(
                    PlanetsAccount,
                    PlanetsAccount.id
                    == PrivateObservationBatch.observer_planets_account_id,
                )
                .where(PlanetsAccount.is_active.is_(True))
                .order_by(
                    PrivateObservationBatch.observer_planets_account_id,
                    PrivateObservationBatch.game_id,
                    PrivateObservationBatch.turn.desc(),
                    PrivateObservationBatch.observed_at.desc(),
                    PrivateObservationBatch.id.desc(),
                )
            ).scalars().all()
        )

    latest: dict[tuple[int, int], tuple[int, int, int, int, int]] = {}
    for batch in rows:
        key = (int(batch.observer_planets_account_id), int(batch.game_id))
        if key in latest:
            continue
        latest[key] = (
            int(batch.id),
            int(batch.observer_planets_account_id),
            int(batch.game_id),
            int(batch.turn),
            int(batch.source_player_slot_id),
        )
    return sorted(latest.values(), key=lambda row: (row[1], row[2]))


def _payload(ship: ShipObservation) -> dict[str, Any]:
    return dict(ship.payload) if isinstance(ship.payload, dict) else {}


def _hull_names(hulls: list[Mapping[str, Any]]) -> dict[int, str]:
    result: dict[int, str] = {}
    for hull in hulls:
        hull_id = payload_integer(hull, "id")
        name = hull.get("name")
        if hull_id is not None and hull_id > 0 and isinstance(name, str):
            result[hull_id] = name
    return result


def _strict_speed_multiplier(
    *,
    hull_id: int | None,
    hull_names: Mapping[int, str],
) -> float | None:
    if hull_id is None or hull_id <= 0:
        return None
    name = hull_names.get(hull_id)
    if name is None:
        return None
    return 2.0 if name.casefold() in GRAVITONIC_HULL_NAMES else 1.0


def _state(
    ship: ShipObservation,
    *,
    hulls: list[Mapping[str, Any]],
    hull_names: Mapping[int, str],
) -> TowShipState:
    payload = _payload(ship)
    return TowShipState(
        ship_id=int(ship.ship_id),
        x=int(ship.x) if ship.x is not None else None,
        y=int(ship.y) if ship.y is not None else None,
        warp=(
            int(ship.warp)
            if ship.warp is not None
            else payload_integer(payload, "warp")
        ),
        waypoint_x=payload_integer(
            payload,
            "waypointx",
            "targetx",
            "waypoint_x",
        ),
        waypoint_y=payload_integer(
            payload,
            "waypointy",
            "targety",
            "waypoint_y",
        ),
        fuel=payload_integer(payload, "neutronium", "fuel"),
        engine_count=hull_engine_count(hull_id=ship.hull_id, hulls=hulls),
        speed_multiplier=_strict_speed_multiplier(
            hull_id=ship.hull_id,
            hull_names=hull_names,
        ),
    )


def run() -> dict[str, Any]:
    groups = _latest_factual_groups()
    summary: Counter[str] = Counter()
    summary["latest_factual_groups"] = len(groups)
    status_counts: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    group_errors: list[dict[str, Any]] = []

    for batch_id, linked_account_id, game_id, turn, owner_slot_id in groups:
        with SessionLocal() as session:
            ships = list(
                session.execute(
                    select(ShipObservation).where(
                        ShipObservation.batch_id == batch_id,
                    )
                ).scalars().all()
            )
            catalog = session.execute(
                select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
            ).scalar_one_or_none()

        if catalog is None:
            summary["catalog_missing_groups"] += 1
            group_errors.append(
                {
                    "linked_account_id": linked_account_id,
                    "game_id": game_id,
                    "turn": turn,
                    "reason": "No persisted game rule catalog is available",
                }
            )
            continue

        settings = dict(catalog.settings)
        unlimited_fuel = bool(settings.get("unlimitedfuel", False))
        if unlimited_fuel:
            summary["unlimited_fuel_groups"] += 1
        else:
            summary["fuel_enabled_groups"] += 1

        hulls = list(catalog.hulls)
        hull_names = _hull_names(hulls)
        states = {
            int(ship.ship_id): _state(
                ship,
                hulls=hulls,
                hull_names=hull_names,
            )
            for ship in ships
        }
        observations = {int(ship.ship_id): ship for ship in ships}

        owner_ships = [ship for ship in ships if ship.owner_id == owner_slot_id]
        summary["owner_ships"] += len(owner_ships)
        attempts: list[TowAttempt] = []
        for ship in owner_ships:
            payload = _payload(ship)
            if not payload_is_tow_mission(payload):
                continue
            summary["factual_tow_missions"] += 1
            target_id = payload_tow_target_id(payload)
            if target_id is None:
                summary["tow_missions_missing_target"] += 1
            else:
                summary["tow_missions_with_target"] += 1
                if target_id in observations:
                    summary["tow_targets_visible"] += 1
                else:
                    summary["tow_targets_not_visible"] += 1
            attempts.append(TowAttempt(int(ship.ship_id), target_id))

        if not attempts:
            continue
        summary["groups_with_tow"] += 1

        target_counts = Counter(
            attempt.target_ship_id
            for attempt in attempts
            if attempt.target_ship_id is not None
        )
        summary["same_target_contest_groups"] += int(
            any(count > 1 for count in target_counts.values())
        )
        tower_ids = {attempt.tower_ship_id for attempt in attempts}
        summary["tow_chain_groups"] += int(
            any(
                attempt.target_ship_id in tower_ids
                for attempt in attempts
                if attempt.target_ship_id is not None
            )
        )

        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=attempts,
            unlimited_fuel=unlimited_fuel,
        )
        for result in resolution.attempts:
            status_counts[result.status.value] += 1
            summary["tow_attempts_evaluated"] += 1
            if result.locked:
                summary["strict_locked_candidates"] += 1
            if not result.certain:
                summary["uncertain_attempts"] += 1

            if len(samples) >= SAMPLE_LIMIT:
                continue
            tower_obs = observations.get(result.tower_ship_id)
            target_obs = (
                observations.get(result.target_ship_id)
                if result.target_ship_id is not None
                else None
            )
            tower_state = states.get(result.tower_ship_id)
            target_state = (
                states.get(result.target_ship_id)
                if result.target_ship_id is not None
                else None
            )
            samples.append(
                {
                    "linked_account_id": linked_account_id,
                    "game_id": game_id,
                    "turn": turn,
                    "unlimited_fuel": unlimited_fuel,
                    "tower_ship_id": result.tower_ship_id,
                    "tower_name": tower_obs.name if tower_obs is not None else None,
                    "target_ship_id": result.target_ship_id,
                    "target_name": target_obs.name if target_obs is not None else None,
                    "status": result.status.value,
                    "certain": result.certain,
                    "reason": result.reason,
                    "tower_position": (
                        [tower_state.x, tower_state.y]
                        if tower_state is not None
                        else None
                    ),
                    "target_position": (
                        [target_state.x, target_state.y]
                        if target_state is not None
                        else None
                    ),
                    "tower_warp": tower_state.warp if tower_state is not None else None,
                    "target_warp": target_state.warp if target_state is not None else None,
                    "tower_engine_count": (
                        tower_state.engine_count if tower_state is not None else None
                    ),
                    "target_engine_count": (
                        target_state.engine_count if target_state is not None else None
                    ),
                    "tower_fuel": tower_state.fuel if tower_state is not None else None,
                    "target_fuel": target_state.fuel if target_state is not None else None,
                    "target_waypoint": (
                        [target_state.waypoint_x, target_state.waypoint_y]
                        if target_state is not None
                        else None
                    ),
                }
            )

    ordered_summary = {
        key: int(summary.get(key, 0))
        for key in (
            "latest_factual_groups",
            "catalog_missing_groups",
            "unlimited_fuel_groups",
            "fuel_enabled_groups",
            "owner_ships",
            "groups_with_tow",
            "factual_tow_missions",
            "tow_missions_missing_target",
            "tow_missions_with_target",
            "tow_targets_visible",
            "tow_targets_not_visible",
            "same_target_contest_groups",
            "tow_chain_groups",
            "tow_attempts_evaluated",
            "strict_locked_candidates",
            "uncertain_attempts",
        )
    }

    return {
        "diagnostic": "movement_tow_runtime",
        "read_only": True,
        "summary": ordered_summary,
        "status_counts": dict(sorted(status_counts.items())),
        "samples": samples,
        "group_errors": group_errors,
        "notes": [
            "Tow mission ID 6 and mission1target are read only from the controlling player's factual private snapshot.",
            "The diagnostic audits latest factual state for every active linked observer/game pair and does not write order drafts or canonical observations.",
            "Unique Tow candidates use the strict planets-lab lock subset: valid target, tower engine eligibility, fuel where finite, colocation, and four-fingers target break when factual inputs are available.",
            "Same-target Tow contests and Tow chains/cycles fail closed; no winning tower identity is inferred from ship ID ordering.",
            "Route-equivalent historical Tow movement is TESTED + DIFF_VERIFIED in planets-lab, but this diagnostic does not promote a predicted route until lock prerequisites are factual and unique.",
            "Unknown target fuel/engines/waypoint remains unknown rather than becoming zero.",
        ],
    }


def main() -> None:
    json.dump(run(), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
