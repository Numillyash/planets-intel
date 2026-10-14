from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation


INTERCEPT_MISSION_ID = 7
SAMPLE_LIMIT = 50


def _payload(ship: ShipObservation) -> dict[str, Any]:
    return dict(ship.payload) if isinstance(ship.payload, dict) else {}


def _payload_int(payload: dict[str, Any], *keys: str) -> int | None:
    wanted = {key.casefold() for key in keys}
    for key, value in payload.items():
        if key.casefold() not in wanted or isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


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


def run() -> dict[str, Any]:
    summary: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    group_errors: list[dict[str, Any]] = []
    groups = _latest_factual_groups()
    summary["latest_factual_groups"] = len(groups)

    for batch_id, linked_account_id, game_id, turn, owner_slot_id in groups:
        with SessionLocal() as session:
            ships = list(
                session.execute(
                    select(ShipObservation).where(ShipObservation.batch_id == batch_id)
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

        unlimited_fuel = bool(dict(catalog.settings).get("unlimitedfuel", False))
        summary[
            "unlimited_fuel_groups" if unlimited_fuel else "fuel_enabled_groups"
        ] += 1

        observations = {int(ship.ship_id): ship for ship in ships}
        owner_ships = [ship for ship in ships if ship.owner_id == owner_slot_id]
        summary["owner_ships"] += len(owner_ships)

        group_intercepts = 0
        for ship in owner_ships:
            payload = _payload(ship)
            if _payload_int(payload, "mission") != INTERCEPT_MISSION_ID:
                continue

            group_intercepts += 1
            summary["factual_intercept_missions"] += 1
            if unlimited_fuel:
                summary["unlimited_fuel_intercepts"] += 1
            else:
                summary["fuel_enabled_intercepts"] += 1

            target_id = _payload_int(
                payload,
                "mission1target",
                "mission1_target_id",
                "mission1targetid",
            )
            if target_id is None or target_id <= 0:
                summary["intercepts_missing_target"] += 1
            else:
                summary["intercepts_with_target"] += 1
                if target_id in observations:
                    summary["intercept_targets_visible"] += 1
                else:
                    summary["intercept_targets_not_visible"] += 1

            warp = (
                int(ship.warp)
                if ship.warp is not None
                else _payload_int(payload, "warp")
            )
            if warp is None:
                summary["intercept_warp_unknown"] += 1
            elif warp <= 0:
                summary["intercept_warp_zero"] += 1
            else:
                summary["intercept_warp_positive"] += 1

            fuel = _payload_int(payload, "neutronium", "fuel")
            if fuel is None:
                summary["intercept_snapshot_fuel_unknown"] += 1
            elif fuel <= 0:
                summary["intercept_snapshot_fuel_nonpositive"] += 1
            else:
                summary["intercept_snapshot_fuel_positive"] += 1

            if len(samples) < SAMPLE_LIMIT:
                target = observations.get(target_id) if target_id is not None else None
                samples.append(
                    {
                        "linked_account_id": linked_account_id,
                        "game_id": game_id,
                        "turn": turn,
                        "unlimited_fuel": unlimited_fuel,
                        "ship_id": int(ship.ship_id),
                        "ship_name": ship.name,
                        "owner_slot_id": owner_slot_id,
                        "warp": warp,
                        "snapshot_fuel": fuel,
                        "target_ship_id": target_id,
                        "target_visible": target is not None,
                        "target_name": target.name if target is not None else None,
                    }
                )

        if group_intercepts:
            summary["groups_with_intercept"] += 1

    ordered_summary = {
        key: int(summary.get(key, 0))
        for key in (
            "latest_factual_groups",
            "catalog_missing_groups",
            "unlimited_fuel_groups",
            "fuel_enabled_groups",
            "owner_ships",
            "groups_with_intercept",
            "factual_intercept_missions",
            "unlimited_fuel_intercepts",
            "fuel_enabled_intercepts",
            "intercepts_missing_target",
            "intercepts_with_target",
            "intercept_targets_visible",
            "intercept_targets_not_visible",
            "intercept_warp_unknown",
            "intercept_warp_zero",
            "intercept_warp_positive",
            "intercept_snapshot_fuel_unknown",
            "intercept_snapshot_fuel_nonpositive",
            "intercept_snapshot_fuel_positive",
        )
    }

    return {
        "diagnostic": "movement_intercept_runtime",
        "read_only": True,
        "summary": ordered_summary,
        "samples": samples,
        "group_errors": group_errors,
        "notes": [
            "Mission ID 7 and mission1target are read only from the controlling player's latest factual private snapshot.",
            "Snapshot neutronium is reported only as evidence availability; it is not treated as Intercept-phase fuel after earlier Host phases.",
            "Unlimited-fuel games retain the verified geometry pipeline. Moving finite-fuel Intercept endpoints remain fail-closed until historical differential validation establishes their fuel/phase semantics.",
            "The diagnostic does not write drafts, canonical observations, or inferred movement facts.",
        ],
    }


def main() -> None:
    json.dump(run(), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
