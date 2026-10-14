from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch


SAMPLE_LIMIT = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only factual coverage audit for persisted VCRs. It reports which "
            "combat shapes, races, hulls and equipment patterns are actually present "
            "in the stored corpus. Coverage is evidence of exercised inputs only; it "
            "does not prove that every Host special rule is implemented correctly."
        )
    )
    parser.add_argument(
        "--game-id",
        type=int,
        default=None,
        help="Restrict the audit to one game. Default: all games with stored VCRs.",
    )
    return parser.parse_args()


def _integer(record: dict[str, Any] | None, key: str) -> int | None:
    if not isinstance(record, dict):
        return None
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _boolean(record: dict[str, Any] | None, key: str) -> bool | None:
    if not isinstance(record, dict):
        return None
    value = record.get(key)
    return value if isinstance(value, bool) else None


def _text(record: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(record, dict):
        return None
    value = record.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _side_profile(record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {"present": False, "kind": "missing"}

    hull_id = _integer(record, "hullid")
    if hull_id is None:
        kind = "unknown"
    elif hull_id <= 0:
        kind = "planet"
    else:
        kind = "ship"

    beam_count = _integer(record, "beamcount")
    launcher_count = _integer(record, "launchercount")
    bay_count = _integer(record, "baycount")
    mass = _integer(record, "mass")
    damage = _integer(record, "damage")
    shield = _integer(record, "shield")
    weapon_counts_known = all(
        isinstance(value, int)
        for value in (beam_count, launcher_count, bay_count)
    )

    return {
        "present": True,
        "kind": kind,
        "object_id": _integer(record, "objectid"),
        "name": _text(record, "name"),
        "hull_id": hull_id,
        "race_id": _integer(record, "raceid"),
        "has_starbase": _boolean(record, "hasstarbase"),
        "beam_count": beam_count,
        "launcher_count": launcher_count,
        "bay_count": bay_count,
        "mass": mass,
        "damage": damage,
        "shield": shield,
        "carrier": kind == "ship" and bay_count is not None and bay_count > 0,
        "torpedo_ship": (
            kind == "ship"
            and launcher_count is not None
            and launcher_count > 0
        ),
        "beam_armed": kind == "ship" and beam_count is not None and beam_count > 0,
        "unarmed_ship": (
            kind == "ship"
            and weapon_counts_known
            and beam_count == 0
            and launcher_count == 0
            and bay_count == 0
        ),
        "damaged_start": damage is not None and damage > 0,
        "sub_full_shield_start": shield is not None and shield < 100,
    }


def _case_profile(payload: dict[str, Any]) -> dict[str, Any]:
    left = _side_profile(payload.get("left"))
    right = _side_profile(payload.get("right"))
    shape = f"{left['kind']}_vs_{right['kind']}"

    sides = (left, right)
    ship_sides = [side for side in sides if side["kind"] == "ship"]
    planet_sides = [side for side in sides if side["kind"] == "planet"]
    carriers = [side for side in ship_sides if side["carrier"]]
    torpedo_ships = [side for side in ship_sides if side["torpedo_ship"]]

    right_balance_candidate_shape = bool(
        left["kind"] == "ship"
        and left["carrier"]
        and right["kind"] == "ship"
        and isinstance(right.get("mass"), int)
        and right["mass"] >= 140
    )

    return {
        "shape": shape,
        "left": left,
        "right": right,
        "ship_vs_planet": len(ship_sides) == 1 and len(planet_sides) == 1,
        "starbase_battle": any(
            side.get("has_starbase") is True for side in planet_sides
        ),
        "carrier_battle": bool(carriers),
        "carrier_vs_carrier": len(carriers) == 2,
        "carrier_and_torpedo_ship": bool(carriers) and bool(torpedo_ships),
        "torpedo_ship_battle": bool(torpedo_ships),
        "damaged_start": any(side["damaged_start"] for side in sides),
        "sub_full_shield_start": any(side["sub_full_shield_start"] for side in sides),
        "unarmed_ship_present": any(side["unarmed_ship"] for side in ship_sides),
        "federation_ship_battle": any(
            side.get("race_id") == 1 for side in ship_sides
        ),
        "lizard_ship_battle": any(side.get("race_id") == 2 for side in ship_sides),
        "federation_ship_vs_planet": (
            len(planet_sides) == 1
            and any(side.get("race_id") == 1 for side in ship_sides)
        ),
        "lizard_ship_vs_planet": (
            len(planet_sides) == 1
            and any(side.get("race_id") == 2 for side in ship_sides)
        ),
        "right_balance_candidate_shape": right_balance_candidate_shape,
    }


def _catalog_name_map(records: list[dict[str, Any]]) -> dict[int, str]:
    result: dict[int, str] = {}
    for record in records:
        item_id = _integer(record, "id")
        name = _text(record, "name")
        if item_id is not None and name is not None:
            result[item_id] = name
    return result


def _sample(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "game_id": case["game_id"],
        "turn": case["turn"],
        "vcr_id": case["vcr_id"],
        "left": {
            "id": case["profile"]["left"].get("object_id"),
            "name": case["profile"]["left"].get("name"),
            "hull_id": case["profile"]["left"].get("hull_id"),
            "race_id": case["profile"]["left"].get("race_id"),
        },
        "right": {
            "id": case["profile"]["right"].get("object_id"),
            "name": case["profile"]["right"].get("name"),
            "hull_id": case["profile"]["right"].get("hull_id"),
            "race_id": case["profile"]["right"].get("race_id"),
        },
    }


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
            CombatObservation.battle_turn.desc(),
            CombatObservation.vcr_id.desc(),
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )
        rows = session.execute(query).all()

        game_ids = sorted({int(batch.game_id) for _combat, batch in rows})
        catalogs = {
            int(catalog.game_id): catalog
            for catalog in session.execute(
                select(GameRuleCatalog).where(GameRuleCatalog.game_id.in_(game_ids))
            ).scalars().all()
        } if game_ids else {}

    grouped: dict[tuple[int, int, int], list[tuple[CombatObservation, PrivateObservationBatch]]] = defaultdict(list)
    for combat, batch in rows:
        grouped[(int(batch.game_id), int(combat.battle_turn), int(combat.vcr_id))].append((combat, batch))

    cases: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: (item[0], item[1], item[2])):
        game_id, turn, vcr_id = key
        combat, _batch = grouped[key][0]
        payload = dict(combat.payload) if isinstance(combat.payload, dict) else {}
        cases.append(
            {
                "game_id": game_id,
                "turn": turn,
                "vcr_id": vcr_id,
                "profile": _case_profile(payload),
            }
        )

    battle_shapes: Counter[str] = Counter()
    mechanics: dict[str, dict[str, Any]] = {
        name: {"count": 0, "samples": []}
        for name in (
            "ship_vs_planet",
            "starbase_battle",
            "carrier_battle",
            "carrier_vs_carrier",
            "carrier_and_torpedo_ship",
            "torpedo_ship_battle",
            "damaged_start",
            "sub_full_shield_start",
            "unarmed_ship_present",
            "federation_ship_battle",
            "lizard_ship_battle",
            "federation_ship_vs_planet",
            "lizard_ship_vs_planet",
            "right_balance_candidate_shape",
        )
    }
    race_stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "ship_side_appearances": 0,
            "ship_battles": 0,
            "carrier_side_appearances": 0,
            "planet_side_appearances": 0,
            "samples": [],
        }
    )
    hull_stats: Counter[tuple[int, int]] = Counter()
    game_counts: Counter[int] = Counter()

    for case in cases:
        profile = case["profile"]
        battle_shapes[profile["shape"]] += 1
        game_counts[case["game_id"]] += 1

        for mechanic_name, bucket in mechanics.items():
            if not profile[mechanic_name]:
                continue
            bucket["count"] += 1
            if len(bucket["samples"]) < SAMPLE_LIMIT:
                bucket["samples"].append(_sample(case))

        races_in_ship_battle: set[int] = set()
        for side_name in ("left", "right"):
            side = profile[side_name]
            race_id = side.get("race_id")
            if not isinstance(race_id, int):
                continue
            if side["kind"] == "ship":
                race_stats[race_id]["ship_side_appearances"] += 1
                races_in_ship_battle.add(race_id)
                if side["carrier"]:
                    race_stats[race_id]["carrier_side_appearances"] += 1
                hull_id = side.get("hull_id")
                if isinstance(hull_id, int) and hull_id > 0:
                    hull_stats[(case["game_id"], hull_id)] += 1
            elif side["kind"] == "planet":
                race_stats[race_id]["planet_side_appearances"] += 1

        for race_id in races_in_ship_battle:
            race_stats[race_id]["ship_battles"] += 1
            if len(race_stats[race_id]["samples"]) < SAMPLE_LIMIT:
                race_stats[race_id]["samples"].append(_sample(case))

    hull_rows: list[dict[str, Any]] = []
    name_maps = {
        game_id: _catalog_name_map(list(catalog.hulls))
        for game_id, catalog in catalogs.items()
    }
    for (game_id, hull_id), appearances in sorted(
        hull_stats.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
    ):
        hull_rows.append(
            {
                "game_id": game_id,
                "hull_id": hull_id,
                "name": name_maps.get(game_id, {}).get(hull_id),
                "ship_side_appearances": appearances,
            }
        )

    return {
        "diagnostic": "combat_corpus_coverage",
        "read_only": True,
        "filters": {"game_id": args.game_id},
        "summary": {
            "stored_observations": len(rows),
            "unique_vcrs": len(cases),
            "games": len(game_counts),
            "race_ids_with_ship_combat": len(
                [race_id for race_id, row in race_stats.items() if row["ship_side_appearances"]]
            ),
            "unique_game_hulls_in_combat": len(hull_stats),
        },
        "games": {str(game_id): count for game_id, count in sorted(game_counts.items())},
        "battle_shapes": dict(sorted(battle_shapes.items())),
        "mechanics": mechanics,
        "races": {str(race_id): row for race_id, row in sorted(race_stats.items())},
        "hulls": hull_rows,
        "notes": [
            "This report classifies factual VCR inputs; it does not assert that a Host special rule fired.",
            "Unknown hull/starbase/weapon fields remain unknown and are not collapsed to ship/false/zero classifications.",
            "right_balance_candidate_shape mirrors only the current simulator eligibility shape: LEFT carrier vs RIGHT ship with mass >= 140.",
            "Race and hull coverage shows exercised inputs, not proof of exact special-race mechanics.",
            "Samples are stable references for targeted follow-up regression checks.",
        ],
    }


def main() -> None:
    json.dump(run(parse_args()), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
