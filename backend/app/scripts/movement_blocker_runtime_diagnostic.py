from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.movement_prediction_effective import (
    MovementPredictionAccessError,
    MovementPredictionNotFound,
    get_effective_movement_prediction,
)


SAMPLE_LIMIT_PER_BLOCKER = 12
_UNKNOWN_BLOCKER = "unclassified_unknown"


def _current_batches() -> list[
    tuple[PrivateObservationBatch, PlanetsAccount, Game]
]:
    """Return the newest current-turn factual batch for each active account/game.

    A stored private snapshot is considered current only when its turn matches
    the canonical games.current_turn value. Stale snapshots are deliberately
    excluded so this diagnostic measures the same current-state boundary used
    by Turn Review rather than replaying historical rows as if they were live.
    """

    with SessionLocal() as session:
        rows = list(
            session.execute(
                select(PrivateObservationBatch, PlanetsAccount, Game)
                .join(
                    PlanetsAccount,
                    PlanetsAccount.id
                    == PrivateObservationBatch.observer_planets_account_id,
                )
                .join(Game, Game.id == PrivateObservationBatch.game_id)
                .where(
                    PlanetsAccount.is_active.is_(True),
                    PrivateObservationBatch.turn == Game.current_turn,
                )
                .order_by(
                    PrivateObservationBatch.observer_planets_account_id,
                    PrivateObservationBatch.game_id,
                    PrivateObservationBatch.observed_at.desc(),
                    PrivateObservationBatch.id.desc(),
                )
            ).all()
        )

    latest: dict[
        tuple[int, int],
        tuple[PrivateObservationBatch, PlanetsAccount, Game],
    ] = {}
    for batch, account, game in rows:
        key = (int(account.id), int(game.id))
        if key not in latest:
            latest[key] = (batch, account, game)

    return sorted(
        latest.values(),
        key=lambda row: (int(row[1].id), int(row[2].id)),
    )


def _is_predicted(item: dict[str, Any]) -> bool:
    return (
        bool(item.get("certain"))
        and item.get("predicted_x") is not None
        and item.get("predicted_y") is not None
    )


def _phase_key(item: dict[str, Any]) -> str:
    phase = str(item.get("phase") or "unknown")
    if phase == "tow":
        role = str(item.get("tow_role") or "unknown")
        return f"tow:{role}"
    return phase


def _blocker_key(item: dict[str, Any]) -> str | None:
    if _is_predicted(item):
        return None
    value = item.get("blocker_class")
    if isinstance(value, str) and value:
        return value
    return _UNKNOWN_BLOCKER


def summarize_prediction_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    summary = Counter()
    blocker_counts: Counter[str] = Counter()
    phase_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    fuel_status_counts: Counter[str] = Counter()
    blocker_phase_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for item in items:
        summary["prediction_items"] += 1
        phase = _phase_key(item)
        phase_counts[phase] += 1
        status_counts[str(item.get("status") or "unknown")] += 1
        fuel_status_counts[str(item.get("fuel_status") or "unknown")] += 1

        blocker = _blocker_key(item)
        if blocker is None:
            summary["predicted_items"] += 1
            continue

        summary["unknown_items"] += 1
        blocker_counts[blocker] += 1
        blocker_phase_counts[blocker][phase] += 1

    return {
        "summary": {
            "prediction_items": int(summary["prediction_items"]),
            "predicted_items": int(summary["predicted_items"]),
            "unknown_items": int(summary["unknown_items"]),
        },
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "phase_counts": dict(sorted(phase_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "fuel_status_counts": dict(sorted(fuel_status_counts.items())),
        "blocker_phase_counts": {
            blocker: dict(sorted(counts.items()))
            for blocker, counts in sorted(blocker_phase_counts.items())
        },
    }


def _sample_item(
    *,
    item: dict[str, Any],
    account: PlanetsAccount,
    game: Game,
    batch: PrivateObservationBatch,
) -> dict[str, Any]:
    return {
        "user_id": int(account.user_id),
        "linked_account_id": int(account.id),
        "planets_username": account.planets_username,
        "game_id": int(game.id),
        "game_name": game.name,
        "game_status": game.status_name,
        "turn": int(batch.turn),
        "batch_id": int(batch.id),
        "ship_id": item.get("ship_id"),
        "phase": item.get("phase"),
        "tow_role": item.get("tow_role"),
        "status": item.get("status"),
        "certain": item.get("certain"),
        "blocker_class": _blocker_key(item),
        "blocker_reason": item.get("blocker_reason"),
        "fuel_status": item.get("fuel_status"),
        "fuel_basis": item.get("fuel_basis"),
        "fuel_reason": item.get("fuel_reason"),
        "tow_lock_status": item.get("tow_lock_status"),
        "tow_tower_ship_id": item.get("tow_tower_ship_id"),
        "tow_target_ship_id": item.get("tow_target_ship_id"),
        "reason": item.get("reason"),
        "warnings": list(item.get("warnings") or []),
    }


def run() -> dict[str, Any]:
    groups = _current_batches()
    all_items: list[dict[str, Any]] = []
    group_summaries: list[dict[str, Any]] = []
    group_errors: list[dict[str, Any]] = []
    samples_by_blocker: dict[str, list[dict[str, Any]]] = defaultdict(list)

    groups_with_items = 0

    for batch, account, game in groups:
        try:
            prediction = get_effective_movement_prediction(
                user_id=int(account.user_id),
                linked_account_id=int(account.id),
                game_id=int(game.id),
                turn=int(batch.turn),
            )
        except (MovementPredictionAccessError, MovementPredictionNotFound) as exc:
            group_errors.append(
                {
                    "linked_account_id": int(account.id),
                    "game_id": int(game.id),
                    "game_name": game.name,
                    "turn": int(batch.turn),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        except Exception as exc:  # diagnostic: preserve concrete runtime failure
            group_errors.append(
                {
                    "linked_account_id": int(account.id),
                    "game_id": int(game.id),
                    "game_name": game.name,
                    "turn": int(batch.turn),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        raw_items = prediction.get("items")
        items = [
            dict(item)
            for item in raw_items
            if isinstance(item, dict)
        ] if isinstance(raw_items, list) else []

        if items:
            groups_with_items += 1
        all_items.extend(items)

        local = summarize_prediction_items(items)
        group_summaries.append(
            {
                "linked_account_id": int(account.id),
                "planets_username": account.planets_username,
                "game_id": int(game.id),
                "game_name": game.name,
                "game_status": game.status_name,
                "turn": int(batch.turn),
                "batch_id": int(batch.id),
                "prediction_items": local["summary"]["prediction_items"],
                "predicted_items": local["summary"]["predicted_items"],
                "unknown_items": local["summary"]["unknown_items"],
                "blocker_counts": local["blocker_counts"],
            }
        )

        for item in items:
            blocker = _blocker_key(item)
            if blocker is None:
                continue
            samples = samples_by_blocker[blocker]
            if len(samples) >= SAMPLE_LIMIT_PER_BLOCKER:
                continue
            samples.append(
                _sample_item(
                    item=item,
                    account=account,
                    game=game,
                    batch=batch,
                )
            )

    aggregate = summarize_prediction_items(all_items)
    aggregate["summary"].update(
        {
            "current_factual_groups": len(groups),
            "groups_with_prediction_items": groups_with_items,
            "groups_with_errors": len(group_errors),
        }
    )

    return {
        "diagnostic": "movement_blocker_runtime",
        "read_only": True,
        **aggregate,
        "samples_by_blocker": {
            blocker: samples
            for blocker, samples in sorted(samples_by_blocker.items())
        },
        "group_summaries": group_summaries,
        "group_errors": group_errors,
        "notes": [
            "Only factual private batches whose turn equals games.current_turn are audited; stale snapshots are excluded.",
            "Rows come from the effective movement prediction facade used by production, including factual Tow participants that do not have a local ShipOrderDraft.",
            "Blocker provenance is descriptive only and never upgrades an UNKNOWN endpoint to PREDICTED.",
            "The diagnostic is read-only and does not modify observations, drafts, game metadata or prediction semantics.",
            "Use blocker_counts and blocker_phase_counts to choose the next evidence-backed implementation transfer; phase_state_required is not an implementation gap.",
        ],
    }


def main() -> int:
    json.dump(run(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
