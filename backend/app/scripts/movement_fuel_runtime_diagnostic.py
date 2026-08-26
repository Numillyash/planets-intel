from __future__ import annotations

import json
import sys
from collections import Counter

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.ship_order_draft import ShipOrderDraft
from app.services.movement_prediction_runtime import (
    MovementPredictionAccessError,
    MovementPredictionNotFound,
    get_draft_movement_prediction,
)


SAMPLE_LIMIT = 20


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


def run() -> dict:
    groups = _draft_groups()
    status_counts: Counter[str] = Counter()
    summary = {
        "draft_groups": len(groups),
        "groups_resolved": 0,
        "groups_unavailable": 0,
        "items": 0,
        "waypoint_items": 0,
        "intercept_items": 0,
        "fuel_limited_waypoints": 0,
        "fuel_unknown_or_unsupported_waypoints": 0,
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
            status_counts[fuel_status] += 1
            if mode == "waypoint" and fuel_status == "limited":
                summary["fuel_limited_waypoints"] += 1
            if mode == "waypoint" and fuel_status in {
                "unknown",
                "unsupported_zero_fuel",
                "unsupported_partial_waypoint",
                "unsupported_gravitonic",
                "not_evaluated",
            }:
                summary["fuel_unknown_or_unsupported_waypoints"] += 1

            if len(samples) < SAMPLE_LIMIT:
                samples.append(
                    {
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
                    }
                )

    return {
        "diagnostic": "movement_fuel_runtime",
        "read_only": True,
        "summary": summary,
        "fuel_status_counts": dict(sorted(status_counts.items())),
        "samples": samples,
        "group_errors": group_errors,
        "notes": [
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
