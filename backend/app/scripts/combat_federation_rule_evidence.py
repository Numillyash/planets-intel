from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch


FEDERATION_RACE_ID = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only audit of directly observable Federation combat-rule evidence in "
            "stored factual VCRs. It does not infer hidden installed weapons and keeps "
            "between-fight shield recovery unvalidated unless repeated Federation VCRs exist."
        )
    )
    parser.add_argument(
        "--game-id",
        type=int,
        default=None,
        help="Restrict the audit to one game.",
    )
    return parser.parse_args()


def _integer(record: Mapping[str, Any] | None, *keys: str) -> int | None:
    if not isinstance(record, Mapping):
        return None
    for key in keys:
        value = record.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _text(record: Mapping[str, Any] | None, key: str) -> str | None:
    if not isinstance(record, Mapping):
        return None
    value = record.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _catalog_by_id(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for record in records:
        item_id = _integer(record, "id")
        if item_id is not None:
            result[item_id] = record
    return result


def _normal_damage_weapon_limit(damage: int) -> int:
    return max(0, min(10, 10 - max(0, damage) // 10))


def _side_record(
    *,
    game_id: int,
    turn: int,
    vcr_id: int,
    side_name: str,
    payload: Mapping[str, Any],
    hulls: Mapping[int, Mapping[str, Any]],
    x: int | None,
    y: int | None,
) -> dict[str, Any] | None:
    side = payload.get(side_name)
    if not isinstance(side, Mapping):
        return None
    hull_id = _integer(side, "hullid")
    race_id = _integer(side, "raceid")
    if hull_id is None or hull_id <= 0 or race_id != FEDERATION_RACE_ID:
        return None

    hull = hulls.get(hull_id)
    damage = _integer(side, "damage")
    beams = _integer(side, "beamcount")
    launchers = _integer(side, "launchercount")
    bays = _integer(side, "baycount")
    hull_bays = _integer(hull, "fighterbays", "bays")
    normal_limit = _normal_damage_weapon_limit(damage or 0) if damage is not None else None

    damaged_weapon_evidence: dict[str, Any]
    if damage is None or damage <= 0 or normal_limit is None:
        damaged_weapon_evidence = {"status": "not_applicable"}
    elif beams is None or launchers is None:
        damaged_weapon_evidence = {"status": "not_comparable"}
    else:
        exceeds_normal_limit = beams > normal_limit or launchers > normal_limit
        damaged_weapon_evidence = {
            "status": "direct_evidence" if exceeds_normal_limit else "not_exercised_or_not_isolating",
            "normal_non_fed_limit": normal_limit,
            "vcr_beams": beams,
            "vcr_launchers": launchers,
            "exceeds_normal_limit": exceeds_normal_limit,
        }

    carrier_bay_evidence: dict[str, Any]
    if hull_bays is None:
        carrier_bay_evidence = {"status": "not_comparable"}
    elif hull_bays <= 0:
        carrier_bay_evidence = {"status": "not_applicable", "hull_bays": hull_bays}
    elif bays is None:
        carrier_bay_evidence = {"status": "not_comparable", "hull_bays": hull_bays}
    else:
        expected = hull_bays + 3
        carrier_bay_evidence = {
            "status": "match" if bays == expected else "mismatch_or_ruleset_difference",
            "hull_bays": hull_bays,
            "expected_fed_bays": expected,
            "vcr_bays": bays,
            "delta": bays - hull_bays,
        }

    return {
        "game_id": game_id,
        "turn": turn,
        "vcr_id": vcr_id,
        "side": side_name,
        "ship_id": _integer(side, "objectid"),
        "name": _text(side, "name"),
        "hull_id": hull_id,
        "position": [x, y] if x is not None and y is not None else None,
        "start": {
            "damage": damage,
            "shield": _integer(side, "shield"),
            "beam_count": beams,
            "launcher_count": launchers,
            "bay_count": bays,
        },
        "damaged_weapon_continuity": damaged_weapon_evidence,
        "carrier_bay_bonus": carrier_bay_evidence,
    }


def _repeated_same_turn_transitions(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        ship_id = case.get("ship_id")
        if isinstance(ship_id, int):
            grouped[(int(case["game_id"]), int(case["turn"]), ship_id)].append(case)

    transitions: list[dict[str, Any]] = []
    for (game_id, turn, ship_id), items in sorted(grouped.items()):
        items.sort(key=lambda item: int(item["vcr_id"]))
        for previous, current in zip(items, items[1:]):
            if previous.get("position") != current.get("position"):
                continue
            transitions.append(
                {
                    "game_id": game_id,
                    "turn": turn,
                    "ship_id": ship_id,
                    "from_vcr": previous["vcr_id"],
                    "to_vcr": current["vcr_id"],
                    "position": current.get("position"),
                    "from_start_shield": previous["start"].get("shield"),
                    "to_start_shield": current["start"].get("shield"),
                }
            )
    return transitions


def run(args: argparse.Namespace) -> dict[str, Any]:
    with SessionLocal() as session:
        query = (
            select(CombatObservation, PrivateObservationBatch)
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == CombatObservation.batch_id,
            )
        )
        if args.game_id is not None:
            query = query.where(PrivateObservationBatch.game_id == args.game_id)
        query = query.order_by(
            PrivateObservationBatch.game_id,
            CombatObservation.battle_turn,
            CombatObservation.vcr_id,
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )
        rows = list(session.execute(query).all())
        game_ids = sorted({int(batch.game_id) for _combat, batch in rows})
        catalogs = {
            int(catalog.game_id): catalog
            for catalog in session.execute(
                select(GameRuleCatalog).where(GameRuleCatalog.game_id.in_(game_ids))
            ).scalars().all()
        } if game_ids else {}

    grouped: dict[tuple[int, int, int], tuple[CombatObservation, PrivateObservationBatch]] = {}
    for combat, batch in rows:
        key = (int(batch.game_id), int(combat.battle_turn), int(combat.vcr_id))
        grouped.setdefault(key, (combat, batch))

    summary = {
        "stored_observations": len(rows),
        "unique_vcrs": len(grouped),
        "federation_vcrs": 0,
        "federation_ship_side_appearances": 0,
        "catalog_missing": 0,
        "damaged_start": 0,
        "damaged_weapon_direct_evidence": 0,
        "damaged_weapon_not_isolating": 0,
        "carrier_appearances": 0,
        "carrier_bay_matches": 0,
        "carrier_bay_mismatches_or_ruleset_difference": 0,
        "carrier_bay_not_comparable": 0,
        "same_turn_same_location_fed_transitions": 0,
    }
    cases: list[dict[str, Any]] = []

    for (game_id, turn, vcr_id), (combat, _batch) in sorted(grouped.items()):
        payload = dict(combat.payload) if isinstance(combat.payload, dict) else {}
        catalog = catalogs.get(game_id)
        if catalog is None:
            # Count missing only when a Fed side is actually present.
            has_fed = any(
                isinstance(payload.get(side_name), Mapping)
                and _integer(payload.get(side_name), "hullid") not in (None, 0)
                and _integer(payload.get(side_name), "raceid") == FEDERATION_RACE_ID
                for side_name in ("left", "right")
            )
            if has_fed:
                summary["catalog_missing"] += 1
            continue

        hulls = _catalog_by_id(list(catalog.hulls))
        vcr_had_fed = False
        for side_name in ("left", "right"):
            case = _side_record(
                game_id=game_id,
                turn=turn,
                vcr_id=vcr_id,
                side_name=side_name,
                payload=payload,
                hulls=hulls,
                x=int(combat.x) if combat.x is not None else None,
                y=int(combat.y) if combat.y is not None else None,
            )
            if case is None:
                continue
            vcr_had_fed = True
            summary["federation_ship_side_appearances"] += 1
            damage = case["start"].get("damage")
            if isinstance(damage, int) and damage > 0:
                summary["damaged_start"] += 1
                status = case["damaged_weapon_continuity"].get("status")
                if status == "direct_evidence":
                    summary["damaged_weapon_direct_evidence"] += 1
                elif status == "not_exercised_or_not_isolating":
                    summary["damaged_weapon_not_isolating"] += 1

            bay_status = case["carrier_bay_bonus"].get("status")
            if bay_status not in {"not_applicable", "not_comparable"}:
                summary["carrier_appearances"] += 1
                if bay_status == "match":
                    summary["carrier_bay_matches"] += 1
                else:
                    summary["carrier_bay_mismatches_or_ruleset_difference"] += 1
            elif bay_status == "not_comparable" and case["carrier_bay_bonus"].get("hull_bays", 0) not in (0, None):
                summary["carrier_appearances"] += 1
                summary["carrier_bay_not_comparable"] += 1

            cases.append(case)

        if vcr_had_fed:
            summary["federation_vcrs"] += 1

    transitions = _repeated_same_turn_transitions(cases)
    summary["same_turn_same_location_fed_transitions"] = len(transitions)

    return {
        "diagnostic": "combat_federation_rule_evidence",
        "read_only": True,
        "filters": {"game_id": args.game_id},
        "summary": summary,
        "cases": cases,
        "same_turn_transitions": transitions,
        "notes": [
            "Raw VCR beam/launcher counts are treated as factual combat-start effective counts; hidden installed-weapon counts are never invented.",
            "A damaged-start direct-evidence case requires the factual VCR effective beam or launcher count to exceed the normal non-Federation damage limit.",
            "Carrier +3 bays are directly comparable because fighter bays are a static hull property; a mismatch is reported, not auto-corrected, because game advantages may differ by ruleset.",
            "Federation 25% shield recovery between fights requires a repeated same-turn same-location Federation survivor; absence of such a chain leaves that rule unvalidated.",
            "This audit reports evidence coverage only and modifies no factual observations.",
        ],
    }


def main() -> None:
    json.dump(run(parse_args()), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
