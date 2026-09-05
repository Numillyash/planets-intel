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
from app.models.ship_order_draft import ShipOrderDraft
from app.services.movement_fuel_policy import resolve_waypoint_fuel
from app.services.movement_intercept import Point
from app.services.movement_move_most import MoveMostOrder, resolve_move_most_order
from app.services.movement_prediction import (
    _hull_name_by_id,
    _payload_int,
    _speed_multiplier,
)
from app.services.movement_prediction_runtime import (
    MovementPredictionAccessError,
    MovementPredictionNotFound,
    get_draft_movement_prediction,
)


SAMPLE_LIMIT = 30
_UNKNOWN_OR_UNSUPPORTED = {
    "unknown",
    "unsupported_zero_fuel",
    "unsupported_partial_waypoint",
    "unsupported_gravitonic",
    "not_evaluated",
}


def _draft_groups() -> list[tuple[int, int, int, int]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(
                ShipOrderDraft.user_id,
                ShipOrderDraft.linked_account_id,
                ShipOrderDraft.game_id,
                ShipOrderDraft.turn,
            ).distinct()
        ).all()
    return sorted(
        {
            (int(user_id), int(account_id), int(game_id), int(turn))
            for user_id, account_id, game_id, turn in rows
        }
    )


def _latest_factual_groups() -> list[tuple[int, int, int, int, int]]:
    """Return the latest factual batch for every active observer/game pair.

    The diagnostic intentionally does not reuse stale local drafts here. This
    second input path audits the same fuel policy against factual Planets.nu
    waypoint/warp state already present in the latest private snapshot.
    """

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
        key = (
            int(batch.observer_planets_account_id),
            int(batch.game_id),
        )
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


def _factual_waypoint(payload: dict[str, Any]) -> tuple[int, int] | None:
    x = _payload_int(payload, "waypointx", "targetx", "waypoint_x")
    y = _payload_int(payload, "waypointy", "targety", "waypoint_y")
    if x is None or y is None:
        return None
    return x, y


def _append_sample(samples: list[dict], sample: dict) -> None:
    if len(samples) < SAMPLE_LIMIT:
        samples.append(sample)


def _record_status(
    counter: Counter[str],
    summary: dict[str, int],
    *,
    status: str,
    limited_key: str,
    unresolved_key: str,
) -> None:
    counter[status] += 1
    if status == "limited":
        summary[limited_key] += 1
    if status in _UNKNOWN_OR_UNSUPPORTED:
        summary[unresolved_key] += 1


def _audit_factual_waypoints(
    *,
    summary: dict[str, int],
    status_counts: Counter[str],
    samples: list[dict],
) -> list[dict]:
    groups = _latest_factual_groups()
    summary["latest_factual_groups"] = len(groups)
    group_errors: list[dict] = []

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
            summary["factual_catalog_missing"] += 1
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
        hulls = list(catalog.hulls)
        beams = list(catalog.beams)
        torpedoes = list(catalog.torpedos)
        engines = list(catalog.engines)
        hull_names = _hull_name_by_id(catalog)

        for ship in ships:
            if ship.owner_id != owner_slot_id:
                continue
            summary["factual_owner_ships"] += 1
            if ship.x is None or ship.y is None:
                continue
            payload = dict(ship.payload) if isinstance(ship.payload, dict) else {}
            waypoint = _factual_waypoint(payload)
            if waypoint is None:
                continue
            target_x, target_y = waypoint
            if target_x == int(ship.x) and target_y == int(ship.y):
                continue

            summary["factual_waypoint_items"] += 1
            warp = int(ship.warp or 0)
            speed_multiplier = _speed_multiplier(ship, hull_names=hull_names)
            geometric = resolve_move_most_order(
                MoveMostOrder(
                    ship_id=int(ship.ship_id),
                    origin=Point(float(ship.x), float(ship.y)),
                    waypoint=Point(float(target_x), float(target_y)),
                    warp=warp,
                    speed_multiplier=speed_multiplier,
                )
            )
            fuel = resolve_waypoint_fuel(
                unlimited_fuel=unlimited_fuel,
                payload=payload,
                hull_id=ship.hull_id,
                owner_observed=True,
                hulls=hulls,
                beams=beams,
                torpedoes=torpedoes,
                engines=engines,
                warp=warp,
                speed_multiplier=speed_multiplier,
                origin_x=int(ship.x),
                origin_y=int(ship.y),
                target_x=target_x,
                target_y=target_y,
                requested_distance=geometric.requested_distance,
                geometric_moved_distance=geometric.moved_distance,
                geometric_max_distance=geometric.max_distance,
            )
            status = fuel.status.value
            _record_status(
                status_counts,
                summary,
                status=status,
                limited_key="factual_fuel_limited_waypoints",
                unresolved_key="factual_fuel_unknown_or_unsupported_waypoints",
            )
            _append_sample(
                samples,
                {
                    "source": "latest_factual_waypoint",
                    "linked_account_id": linked_account_id,
                    "game_id": game_id,
                    "turn": turn,
                    "ship_id": int(ship.ship_id),
                    "ship_name": ship.name,
                    "warp": warp,
                    "origin": [int(ship.x), int(ship.y)],
                    "waypoint": [target_x, target_y],
                    "requested_distance": geometric.requested_distance,
                    "geometric_moved_distance": geometric.moved_distance,
                    "fuel_status": status,
                    "movement_mass": fuel.movement_mass,
                    "fuel_available": fuel.fuel_available,
                    "fuel_factor": fuel.fuel_factor,
                    "fuel_required": fuel.fuel_required,
                    "fuel_used": fuel.fuel_used,
                    "fuel_limited": fuel.fuel_limited,
                    "fuel_override": (
                        [fuel.override_x, fuel.override_y]
                        if fuel.has_position_override
                        else None
                    ),
                    "certain": fuel.certain,
                    "fuel_reason": fuel.reason,
                    "mass_reason": fuel.mass_reason,
                },
            )

    return group_errors


def run() -> dict:
    groups = _draft_groups()
    draft_status_counts: Counter[str] = Counter()
    factual_status_counts: Counter[str] = Counter()
    summary = {
        "draft_groups": len(groups),
        "groups_resolved": 0,
        "groups_unavailable": 0,
        "items": 0,
        "waypoint_items": 0,
        "intercept_items": 0,
        "fuel_limited_waypoints": 0,
        "fuel_unknown_or_unsupported_waypoints": 0,
        "latest_factual_groups": 0,
        "factual_catalog_missing": 0,
        "factual_owner_ships": 0,
        "factual_waypoint_items": 0,
        "factual_fuel_limited_waypoints": 0,
        "factual_fuel_unknown_or_unsupported_waypoints": 0,
    }
    samples: list[dict] = []
    group_errors: list[dict] = []

    for user_id, linked_account_id, game_id, turn in groups:
        try:
            prediction = get_draft_movement_prediction(
                user_id=user_id,
                linked_account_id=linked_account_id,
                game_id=game_id,
                turn=turn,
            )
        except (MovementPredictionAccessError, MovementPredictionNotFound) as exc:
            summary["groups_unavailable"] += 1
            group_errors.append(
                {
                    "source": "local_draft",
                    "linked_account_id": linked_account_id,
                    "game_id": game_id,
                    "turn": turn,
                    "reason": str(exc),
                }
            )
            continue

        summary["groups_resolved"] += 1
        for item in prediction.get("items", []):
            if not isinstance(item, dict):
                continue
            summary["items"] += 1
            mode = str(item.get("movement_mode") or "unknown")
            if mode == "waypoint":
                summary["waypoint_items"] += 1
            elif mode == "intercept":
                summary["intercept_items"] += 1

            fuel_status = str(item.get("fuel_status") or "not_evaluated")
            if mode == "waypoint":
                _record_status(
                    draft_status_counts,
                    summary,
                    status=fuel_status,
                    limited_key="fuel_limited_waypoints",
                    unresolved_key="fuel_unknown_or_unsupported_waypoints",
                )
            else:
                draft_status_counts[fuel_status] += 1

            _append_sample(
                samples,
                {
                    "source": "local_draft",
                    "linked_account_id": linked_account_id,
                    "game_id": game_id,
                    "turn": turn,
                    "ship_id": item.get("ship_id"),
                    "movement_mode": mode,
                    "warp": item.get("warp"),
                    "requested_distance": item.get("requested_distance"),
                    "moved_distance": item.get("moved_distance"),
                    "predicted": [item.get("predicted_x"), item.get("predicted_y")],
                    "certain": item.get("certain"),
                    "fuel_status": fuel_status,
                    "movement_mass": item.get("movement_mass"),
                    "fuel_available": item.get("fuel_available"),
                    "fuel_factor": item.get("fuel_factor"),
                    "fuel_required": item.get("fuel_required"),
                    "fuel_used": item.get("fuel_used"),
                    "fuel_limited": item.get("fuel_limited"),
                    "fuel_reason": item.get("fuel_reason"),
                },
            )

    factual_errors = _audit_factual_waypoints(
        summary=summary,
        status_counts=factual_status_counts,
        samples=samples,
    )

    return {
        "diagnostic": "movement_fuel_runtime",
        "read_only": True,
        "summary": summary,
        "draft_fuel_status_counts": dict(sorted(draft_status_counts.items())),
        "factual_fuel_status_counts": dict(sorted(factual_status_counts.items())),
        "samples": samples,
        "group_errors": group_errors,
        "factual_group_errors": factual_errors,
        "notes": [
            "Local draft predictions remain restricted to the latest factual turn; stale drafts are reported, never replayed against newer facts.",
            "When current local drafts are absent, latest owner-private Planets.nu waypoint/warp state is audited read-only through the same fuel policy.",
            "Waypoint fuel uses factual owner-private load plus the persisted rule catalog; missing movement-mass fields never become zero.",
            "Positive insufficient fuel is applied only to the normal-speed reachable-waypoint subset already differential-verified in planets-lab.",
            "Zero-fuel, Gravitonic shortage and shortage on an already partial waypoint remain fail-closed.",
            "Finite-fuel Intercept remains an explicitly uncertain geometry preview until Tow and Intercept fuel ordering are integrated.",
            "No factual observations or order drafts are modified.",
        ],
    }


def main() -> None:
    json.dump(run(), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
