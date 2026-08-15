import argparse
import json
import sys
from typing import Any

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_player_slot import GamePlayerSlot
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.planet_observation import PlanetObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.score_observation import ScoreObservation
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation


SHIP_KEYS = (
    "fuel",
    "neutron",
    "duran",
    "tritan",
    "moly",
    "supply",
    "clan",
    "megacredit",
    "fighter",
    "torp",
    "tube",
    "beam",
    "engine",
    "mission",
    "target",
    "waypoint",
    "warp",
    "mass",
    "damage",
    "crew",
    "friendly",
    "cloak",
    "tow",
)

PLANET_KEYS = (
    "colon",
    "native",
    "mine",
    "factor",
    "defense",
    "supply",
    "megacredit",
    "neutron",
    "duran",
    "tritan",
    "moly",
    "tax",
    "happiness",
    "starbase",
    "friendly",
)

BASE_KEYS = (
    "fighter",
    "defense",
    "tech",
    "hull",
    "engine",
    "beam",
    "torp",
    "mission",
    "ship",
    "build",
    "megacredit",
    "duran",
    "tritan",
    "moly",
    "supply",
)

VCR_SIDE_KEYS = (
    "id",
    "name",
    "owner",
    "hull",
    "mass",
    "beam",
    "torp",
    "fighter",
    "damage",
    "shield",
    "crew",
    "starbase",
    "planet",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dump a compact factual war-state snapshot for one observer "
            "and one enemy from the canonical Planets Intel database."
        )
    )
    parser.add_argument("game_id", type=int)
    parser.add_argument("observer")
    parser.add_argument("enemy")
    parser.add_argument(
        "--score-turns",
        type=int,
        default=5,
        help="Number of most recent public-score turns to include.",
    )
    parser.add_argument(
        "--vcr-turns",
        type=int,
        default=6,
        help="Number of most recent turns of enemy VCR evidence to include.",
    )
    return parser.parse_args()


def compact_payload(
    payload: dict[str, Any] | None,
    needles: tuple[str, ...],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    result: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(needle in lowered for needle in needles):
            result[key] = value
    return result


def hull_names(catalog: GameRuleCatalog | None) -> dict[int, str]:
    result: dict[int, str] = {}
    if catalog is None:
        return result

    for row in catalog.hulls:
        if not isinstance(row, dict):
            continue
        hull_id = row.get("id")
        name = row.get("name")
        if isinstance(hull_id, int) and isinstance(name, str):
            result[hull_id] = name
    return result


def vcr_side(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return compact_payload(payload, VCR_SIDE_KEYS)


def run(args: argparse.Namespace) -> dict[str, Any]:
    with SessionLocal() as session:
        observer = session.execute(
            select(PlanetsAccount).where(
                func.lower(PlanetsAccount.planets_username)
                == args.observer.strip().lower()
            )
        ).scalars().first()

        if observer is None:
            raise SystemExit(
                f"observer account {args.observer!r} not found"
            )

        slots = session.execute(
            select(GamePlayerSlot).where(
                GamePlayerSlot.game_id == args.game_id
            )
        ).scalars().all()

        slots_by_name = {
            row.username.strip().casefold(): row
            for row in slots
        }

        own_slot = slots_by_name.get(args.observer.strip().casefold())
        enemy_slot = slots_by_name.get(args.enemy.strip().casefold())

        if own_slot is None:
            raise SystemExit(
                f"observer {args.observer!r} is not a player in game {args.game_id}"
            )
        if enemy_slot is None:
            raise SystemExit(
                f"enemy {args.enemy!r} is not a player in game {args.game_id}"
            )

        latest = session.execute(
            select(PrivateObservationBatch)
            .where(
                PrivateObservationBatch.game_id == args.game_id,
                PrivateObservationBatch.observer_planets_account_id
                == observer.id,
            )
            .order_by(
                PrivateObservationBatch.turn.desc(),
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
        ).scalars().first()

        if latest is None:
            raise SystemExit("no private snapshot found for observer")

        account_ids = list(
            session.execute(
                select(PlanetsAccount.id).where(
                    PlanetsAccount.user_id == observer.user_id,
                    PlanetsAccount.is_active.is_(True),
                )
            ).scalars()
        )

        all_batches = session.execute(
            select(PrivateObservationBatch)
            .where(
                PrivateObservationBatch.game_id == args.game_id,
                PrivateObservationBatch.observer_planets_account_id.in_(
                    account_ids
                ),
            )
            .order_by(
                PrivateObservationBatch.turn.desc(),
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
        ).scalars().all()

        latest_by_account: dict[int, PrivateObservationBatch] = {}
        for batch in all_batches:
            latest_by_account.setdefault(
                int(batch.observer_planets_account_id),
                batch,
            )

        intel_batch_ids = [
            batch.id
            for batch in latest_by_account.values()
        ]

        catalog = session.execute(
            select(GameRuleCatalog).where(
                GameRuleCatalog.game_id == args.game_id
            )
        ).scalar_one_or_none()
        hull_name_by_id = hull_names(catalog)

        own_ships = session.execute(
            select(ShipObservation)
            .where(
                ShipObservation.batch_id == latest.id,
                ShipObservation.owner_id == own_slot.slot_id,
            )
            .order_by(ShipObservation.ship_id)
        ).scalars().all()

        own_ship_dump = [
            {
                "id": ship.ship_id,
                "name": ship.name,
                "hull_id": ship.hull_id,
                "hull_name": hull_name_by_id.get(ship.hull_id),
                "position": [ship.x, ship.y],
                "warp": ship.warp,
                "info_turn": ship.info_turn,
                "state": compact_payload(ship.payload, SHIP_KEYS),
            }
            for ship in own_ships
        ]

        latest_planets = session.execute(
            select(PlanetObservation).where(
                PlanetObservation.batch_id == latest.id
            )
        ).scalars().all()

        planet_names = {
            planet.planet_id: planet.name
            for planet in latest_planets
        }

        own_planets = [
            planet
            for planet in latest_planets
            if planet.owner_id == own_slot.slot_id
        ]
        own_planet_ids = {
            planet.planet_id
            for planet in own_planets
        }

        own_planet_dump = [
            {
                "id": planet.planet_id,
                "name": planet.name,
                "position": [planet.x, planet.y],
                "info_turn": planet.info_turn,
                "state": compact_payload(planet.payload, PLANET_KEYS),
            }
            for planet in sorted(
                own_planets,
                key=lambda item: item.planet_id,
            )
        ]

        own_bases = session.execute(
            select(StarbaseObservation)
            .where(
                StarbaseObservation.batch_id == latest.id
            )
            .order_by(StarbaseObservation.starbase_id)
        ).scalars().all()

        own_base_dump = [
            {
                "id": base.starbase_id,
                "planet_id": base.planet_id,
                "planet": planet_names.get(base.planet_id),
                "info_turn": base.info_turn,
                "state": compact_payload(base.payload, BASE_KEYS),
            }
            for base in own_bases
            if base.planet_id in own_planet_ids
        ]

        enemy_rows = session.execute(
            select(
                ShipObservation,
                PrivateObservationBatch,
            )
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == ShipObservation.batch_id,
            )
            .where(
                ShipObservation.batch_id.in_(intel_batch_ids),
                ShipObservation.owner_id == enemy_slot.slot_id,
            )
        ).all()

        enemy_rows.sort(
            key=lambda row: (
                row[0].info_turn or -1,
                row[1].turn,
                row[1].observed_at,
                row[1].id,
            ),
            reverse=True,
        )

        enemy_seen: dict[int, tuple[ShipObservation, PrivateObservationBatch]] = {}
        for ship, batch in enemy_rows:
            enemy_seen.setdefault(ship.ship_id, (ship, batch))

        enemy_ship_dump = []
        for ship_id in sorted(enemy_seen):
            ship, batch = enemy_seen[ship_id]
            enemy_ship_dump.append(
                {
                    "id": ship.ship_id,
                    "name": ship.name,
                    "hull_id": ship.hull_id,
                    "hull_name": hull_name_by_id.get(ship.hull_id),
                    "position": [ship.x, ship.y],
                    "warp": ship.warp,
                    "info_turn": ship.info_turn,
                    "observer_batch_turn": batch.turn,
                    "state": compact_payload(ship.payload, SHIP_KEYS),
                }
            )

        score_rows = session.execute(
            select(ScoreObservation)
            .where(
                ScoreObservation.game_id == args.game_id,
                ScoreObservation.slot_id.in_(
                    [own_slot.slot_id, enemy_slot.slot_id]
                ),
            )
            .order_by(
                ScoreObservation.turn.desc(),
                ScoreObservation.observed_at.desc(),
            )
        ).scalars().all()

        score_seen: set[tuple[int, int]] = set()
        score_dump = []
        min_score_turn = latest.turn - max(args.score_turns - 1, 0)

        for row in score_rows:
            key = (row.turn, row.slot_id)
            if key in score_seen:
                continue
            score_seen.add(key)
            if row.turn < min_score_turn:
                continue

            score_dump.append(
                {
                    "turn": row.turn,
                    "player": (
                        args.observer
                        if row.slot_id == own_slot.slot_id
                        else args.enemy
                    ),
                    "warships": row.capital_ships,
                    "freighters": row.freighters,
                    "planets": row.planets,
                    "starbases": row.starbases,
                    "military": row.military_score,
                    "inventory": row.inventory_score,
                    "priority_points": row.priority_points,
                }
            )

        vcr_rows = session.execute(
            select(
                CombatObservation,
                PrivateObservationBatch,
            )
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == CombatObservation.batch_id,
            )
            .where(
                PrivateObservationBatch.game_id == args.game_id,
                PrivateObservationBatch.observer_planets_account_id.in_(
                    account_ids
                ),
                (
                    (CombatObservation.left_owner_id == enemy_slot.slot_id)
                    | (CombatObservation.right_owner_id == enemy_slot.slot_id)
                ),
            )
            .order_by(
                CombatObservation.battle_turn.desc(),
                CombatObservation.vcr_id.desc(),
            )
        ).all()

        vcr_seen: set[tuple[int, int]] = set()
        vcr_dump = []
        min_vcr_turn = latest.turn - max(args.vcr_turns - 1, 0)

        for combat, _batch in vcr_rows:
            key = (combat.battle_turn, combat.vcr_id)
            if key in vcr_seen:
                continue
            vcr_seen.add(key)
            if combat.battle_turn < min_vcr_turn:
                continue

            payload = combat.payload if isinstance(combat.payload, dict) else {}
            vcr_dump.append(
                {
                    "turn": combat.battle_turn,
                    "vcr": combat.vcr_id,
                    "position": [combat.x, combat.y],
                    "left": {
                        "owner": combat.left_owner_id,
                        "id": combat.left_object_id,
                        "hull": combat.left_hull_id,
                        "hull_name": hull_name_by_id.get(combat.left_hull_id),
                        "name": combat.left_name,
                        "state": vcr_side(payload.get("left")),
                    },
                    "right": {
                        "owner": combat.right_owner_id,
                        "id": combat.right_object_id,
                        "hull": combat.right_hull_id,
                        "hull_name": hull_name_by_id.get(combat.right_hull_id),
                        "name": combat.right_name,
                        "state": vcr_side(payload.get("right")),
                    },
                }
            )

        return {
            "game_id": args.game_id,
            "turn": latest.turn,
            "observer": {
                "username": args.observer,
                "slot": own_slot.slot_id,
                "race_id": own_slot.race_id,
                "batch_id": latest.id,
            },
            "enemy": {
                "username": args.enemy,
                "slot": enemy_slot.slot_id,
                "race_id": enemy_slot.race_id,
            },
            "own": {
                "ships": own_ship_dump,
                "planets": own_planet_dump,
                "starbases": own_base_dump,
            },
            "known_enemy_ships": enemy_ship_dump,
            "scores_last_turns": score_dump,
            "recent_enemy_vcrs": vcr_dump,
        }


def main() -> None:
    args = parse_args()
    payload = run(args)
    json.dump(
        payload,
        sys.stdout,
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
