from collections import defaultdict
from math import ceil, hypot
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_player_slot import GamePlayerSlot
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.planet_observation import PlanetObservation
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.score_observation import ScoreObservation
from app.models.ship_observation import ShipObservation
from app.models.starbase_observation import StarbaseObservation
from app.services.intel_access import accessible_intel_accounts


WARP_9_DISTANCE = 81.0


def _number(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _integer(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _effective_info_turn(info_turn: int | None, batch_turn: int) -> int:
    if info_turn is not None and info_turn > 0:
        return info_turn
    return batch_turn


def _row_freshness(
    info_turn: int | None,
    batch: PrivateObservationBatch,
) -> tuple[int, object, int]:
    return (
        _effective_info_turn(info_turn, batch.turn),
        batch.observed_at,
        batch.id,
    )


def _by_id(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for record in records:
        item_id = record.get("id")
        if isinstance(item_id, int) and not isinstance(item_id, bool):
            result[item_id] = record
    return result


def _setting_bool(settings: dict[str, Any], *keys: str) -> bool | None:
    wanted = {key.casefold() for key in keys}
    for key, value in settings.items():
        if str(key).casefold() not in wanted:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
    return None


def _safe_name(record: dict[str, Any] | None, fallback: str) -> str:
    if record is not None:
        name = record.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return fallback


def _best_exact_turn_entities(
    *,
    rows: list[tuple[Any, PrivateObservationBatch]],
    id_attr: str,
    info_turn_attr: str,
) -> dict[int, tuple[Any, PrivateObservationBatch]]:
    result: dict[int, tuple[Any, PrivateObservationBatch]] = {}
    for entity, batch in rows:
        entity_id = int(getattr(entity, id_attr))
        current = result.get(entity_id)
        if current is None:
            result[entity_id] = (entity, batch)
            continue
        current_entity, current_batch = current
        if _row_freshness(
            getattr(entity, info_turn_attr), batch
        ) > _row_freshness(
            getattr(current_entity, info_turn_attr), current_batch
        ):
            result[entity_id] = (entity, batch)
    return result


def _combat_equipment(
    *,
    combats: list[tuple[CombatObservation, PrivateObservationBatch]],
    ship_id: int,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for combat, batch in combats:
        payload = combat.payload
        if not isinstance(payload, dict):
            continue
        for side_name in ("left", "right"):
            side = payload.get(side_name)
            if not isinstance(side, dict):
                continue
            if side.get("objectid") != ship_id:
                continue
            candidates.append(
                {
                    "battle_turn": combat.battle_turn,
                    "vcr_id": combat.vcr_id,
                    "batch_id": batch.id,
                    "beam_id": _integer(side, "beamid"),
                    "beam_count": _integer(side, "beamcount"),
                    "torpedo_id": _integer(side, "torpedoid"),
                    "launcher_count": _integer(side, "launchercount"),
                    "torpedoes": _integer(side, "torpedos"),
                    "fighters": _integer(side, "fighters"),
                    "crew": _integer(side, "crew"),
                    "damage": _integer(side, "damage"),
                    "mass": _integer(side, "mass"),
                }
            )

    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item["battle_turn"],
            item["vcr_id"],
            item["batch_id"],
        )
    )
    return candidates[-1]


def _score_context(
    *,
    game_id: int,
    turn: int,
    slot_ids: set[int],
) -> dict[int, dict[str, int | None]]:
    if not slot_ids:
        return {}

    with SessionLocal() as session:
        rows = list(
            session.execute(
                select(ScoreObservation)
                .where(
                    ScoreObservation.game_id == game_id,
                    ScoreObservation.slot_id.in_(slot_ids),
                    ScoreObservation.turn <= turn,
                )
                .order_by(
                    ScoreObservation.slot_id,
                    ScoreObservation.turn,
                )
            ).scalars().all()
        )

    grouped: dict[int, list[ScoreObservation]] = defaultdict(list)
    for row in rows:
        grouped[row.slot_id].append(row)

    result: dict[int, dict[str, int | None]] = {}
    for slot_id, observations in grouped.items():
        current = observations[-1]
        previous = observations[-2] if len(observations) >= 2 else None
        result[slot_id] = {
            "turn": current.turn,
            "military_score": current.military_score,
            "military_delta": (
                current.military_score - previous.military_score
                if previous is not None
                else None
            ),
        }
    return result


def get_ship_threat_analysis(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    ship_id: int,
) -> dict[str, Any] | None:
    if turn <= 0 or ship_id <= 0:
        return None

    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = {account.id for account in accessible}
    if linked_account_id not in accessible_ids or not accessible_ids:
        return None

    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()
        if catalog is None:
            return {
                "game_id": game_id,
                "turn": turn,
                "ship_id": ship_id,
                "status": "catalog_missing",
                "detail": "Game rule catalog is not stored yet; refresh private intel once.",
            }

        primary_batch = session.execute(
            select(PrivateObservationBatch)
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.turn == turn,
                PrivateObservationBatch.observer_planets_account_id
                == linked_account_id,
            )
            .order_by(
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
        ).scalars().first()
        if primary_batch is None:
            return None

        ship_rows = list(
            session.execute(
                select(ShipObservation, PrivateObservationBatch)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == ShipObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.turn == turn,
                    PrivateObservationBatch.observer_planets_account_id.in_(
                        accessible_ids
                    ),
                )
            ).all()
        )
        planet_rows = list(
            session.execute(
                select(PlanetObservation, PrivateObservationBatch)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == PlanetObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.turn == turn,
                    PrivateObservationBatch.observer_planets_account_id.in_(
                        accessible_ids
                    ),
                )
            ).all()
        )
        starbase_rows = list(
            session.execute(
                select(StarbaseObservation, PrivateObservationBatch)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == StarbaseObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.turn == turn,
                    PrivateObservationBatch.observer_planets_account_id.in_(
                        accessible_ids
                    ),
                )
            ).all()
        )
        combat_rows = list(
            session.execute(
                select(CombatObservation, PrivateObservationBatch)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == CombatObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.observer_planets_account_id.in_(
                        accessible_ids
                    ),
                    CombatObservation.battle_turn <= turn,
                )
            ).all()
        )
        mass_rows = list(
            session.execute(
                select(ShipObservation, PrivateObservationBatch)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == ShipObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.turn <= turn,
                    PrivateObservationBatch.observer_planets_account_id.in_(
                        accessible_ids
                    ),
                    ShipObservation.ship_id == ship_id,
                )
            ).all()
        )

        slots = list(
            session.execute(
                select(GamePlayerSlot).where(GamePlayerSlot.game_id == game_id)
            ).scalars().all()
        )

    ships = _best_exact_turn_entities(
        rows=ship_rows,
        id_attr="ship_id",
        info_turn_attr="info_turn",
    )
    planets = _best_exact_turn_entities(
        rows=planet_rows,
        id_attr="planet_id",
        info_turn_attr="info_turn",
    )
    starbases = _best_exact_turn_entities(
        rows=starbase_rows,
        id_attr="starbase_id",
        info_turn_attr="info_turn",
    )

    subject_pair = ships.get(ship_id)
    if subject_pair is None:
        return None
    subject, subject_batch = subject_pair
    subject_payload = subject.payload if isinstance(subject.payload, dict) else {}

    primary_slot_id = primary_batch.source_player_slot_id
    slot_by_id = {slot.slot_id: slot for slot in slots}
    owner_slot = slot_by_id.get(subject.owner_id) if subject.owner_id is not None else None

    hulls = _by_id(catalog.hulls)
    beams = _by_id(catalog.beams)
    torpedos = _by_id(catalog.torpedos)
    races = _by_id(catalog.races)

    hull = hulls.get(subject.hull_id) if subject.hull_id is not None else None
    race = races.get(owner_slot.race_id) if owner_slot is not None else None
    race_name = _safe_name(
        race,
        f"Race #{owner_slot.race_id}" if owner_slot is not None else "Unknown race",
    )

    observed_mass = _integer(subject_payload, "mass")
    historical_masses: dict[int, int] = {}
    for observation, batch in mass_rows:
        payload = observation.payload if isinstance(observation.payload, dict) else {}
        mass = _integer(payload, "mass")
        info_turn = _effective_info_turn(observation.info_turn, batch.turn)
        if mass is not None and mass > 0 and info_turn <= turn:
            historical_masses[info_turn] = mass

    mass_history = [
        {"turn": item_turn, "mass": historical_masses[item_turn]}
        for item_turn in sorted(historical_masses)
    ]
    minimum_observed_mass = min(historical_masses.values()) if historical_masses else observed_mass

    hull_mass = _integer(hull, "mass") if hull is not None else None
    hull_beam_slots = _integer(hull, "beams") if hull is not None else None
    hull_tube_slots = _integer(hull, "launchers") if hull is not None else None
    hull_bays = _integer(hull, "fighterbays") if hull is not None else None

    vcr_equipment = _combat_equipment(
        combats=combat_rows,
        ship_id=ship_id,
    )

    revealed_beam_id = (
        vcr_equipment.get("beam_id")
        if vcr_equipment is not None
        else None
    )
    revealed_torpedo_id = (
        vcr_equipment.get("torpedo_id")
        if vcr_equipment is not None
        else None
    )

    beam_candidates: list[dict[str, Any]] = []
    for beam_id, beam in sorted(beams.items()):
        if isinstance(revealed_beam_id, int) and revealed_beam_id > 0:
            if beam_id != revealed_beam_id:
                continue
        beam_mass = _integer(beam, "mass")
        minimum_mass = None
        if (
            hull_mass is not None
            and hull_beam_slots is not None
            and beam_mass is not None
        ):
            minimum_mass = hull_mass + hull_beam_slots * beam_mass
            if (
                minimum_observed_mass is not None
                and minimum_mass > minimum_observed_mass
            ):
                continue
        beam_candidates.append(
            {
                "id": beam_id,
                "name": _safe_name(beam, f"Beam #{beam_id}"),
                "tech_level": _integer(beam, "techlevel"),
                "mass_each": beam_mass,
                "minimum_hull_plus_beams_mass": minimum_mass,
            }
        )

    torpedo_candidates: list[dict[str, Any]] = []
    for torpedo_id, torpedo in sorted(torpedos.items()):
        if isinstance(revealed_torpedo_id, int) and revealed_torpedo_id > 0:
            if torpedo_id != revealed_torpedo_id:
                continue
        torpedo_candidates.append(
            {
                "id": torpedo_id,
                "name": _safe_name(torpedo, f"Torpedo #{torpedo_id}"),
                "tech_level": _integer(torpedo, "techlevel"),
            }
        )

    waypoint_x = _number(subject_payload, "targetx")
    waypoint_y = _number(subject_payload, "targety")

    owned_planets = [
        planet
        for planet, _batch in planets.values()
        if planet.owner_id == primary_slot_id
        and planet.x is not None
        and planet.y is not None
    ]

    target_planet = None
    target_waypoint_distance = None
    if waypoint_x is not None and waypoint_y is not None and owned_planets:
        target_planet = min(
            owned_planets,
            key=lambda planet: hypot(
                planet.x - waypoint_x,
                planet.y - waypoint_y,
            ),
        )
        target_waypoint_distance = hypot(
            target_planet.x - waypoint_x,
            target_planet.y - waypoint_y,
        )
        if target_waypoint_distance > WARP_9_DISTANCE:
            target_planet = None
            target_waypoint_distance = None

    base_planet_ids = {
        starbase.planet_id
        for starbase, _batch in starbases.values()
        if starbase.planet_id is not None
    }

    target_payload: dict[str, Any] | None = None
    target_distance = None
    target_eta = None
    target_confidence = "none"
    if target_planet is not None:
        target_payload = (
            target_planet.payload
            if isinstance(target_planet.payload, dict)
            else {}
        )
        if subject.x is not None and subject.y is not None:
            target_distance = hypot(
                target_planet.x - subject.x,
                target_planet.y - subject.y,
            )
            if subject.warp is not None and subject.warp > 0:
                target_eta = max(
                    1,
                    ceil(target_distance / float(subject.warp * subject.warp)),
                )
        if target_waypoint_distance is not None:
            if target_waypoint_distance <= 5:
                target_confidence = "very_high"
            elif target_waypoint_distance <= 20:
                target_confidence = "high"
            else:
                target_confidence = "medium"

    def ship_target_distance(candidate: ShipObservation) -> float | None:
        payload = candidate.payload if isinstance(candidate.payload, dict) else {}
        tx = _number(payload, "targetx")
        ty = _number(payload, "targety")
        if target_planet is None or tx is None or ty is None:
            return None
        return hypot(target_planet.x - tx, target_planet.y - ty)

    attack_group: list[dict[str, Any]] = []
    if subject.owner_id is not None:
        for candidate, _batch in ships.values():
            if candidate.owner_id != subject.owner_id:
                continue
            if target_planet is not None:
                waypoint_distance = ship_target_distance(candidate)
                if waypoint_distance is None or waypoint_distance > 35:
                    continue
            payload = candidate.payload if isinstance(candidate.payload, dict) else {}
            attack_group.append(
                {
                    "ship_id": candidate.ship_id,
                    "name": candidate.name,
                    "hull_id": candidate.hull_id,
                    "mass": _integer(payload, "mass"),
                    "x": candidate.x,
                    "y": candidate.y,
                    "warp": candidate.warp,
                    "waypoint_x": _integer(payload, "targetx"),
                    "waypoint_y": _integer(payload, "targety"),
                }
            )
    attack_group.sort(key=lambda item: item["ship_id"])

    defenders: list[dict[str, Any]] = []
    if target_planet is not None:
        for candidate, _batch in ships.values():
            if candidate.owner_id != primary_slot_id:
                continue
            if candidate.x is None or candidate.y is None:
                continue
            distance = hypot(
                target_planet.x - candidate.x,
                target_planet.y - candidate.y,
            )
            if distance > 120:
                continue
            payload = candidate.payload if isinstance(candidate.payload, dict) else {}
            candidate_hull = (
                hulls.get(candidate.hull_id)
                if candidate.hull_id is not None
                else None
            )
            beam_slots = _integer(candidate_hull, "beams") if candidate_hull else None
            tube_slots = _integer(candidate_hull, "launchers") if candidate_hull else None
            bays = _integer(candidate_hull, "fighterbays") if candidate_hull else None
            torpedoes = _integer(payload, "ammo")
            if torpedoes is None:
                torpedoes = _integer(payload, "torps")
            fighters = _integer(payload, "fighters")
            combat_hull = bool(
                (beam_slots or 0) > 0
                or (tube_slots or 0) > 0
                or (bays or 0) > 0
            )
            heavy_weapon_ready = bool(
                ((tube_slots or 0) > 0 and (torpedoes or 0) > 0)
                or ((bays or 0) > 0 and (fighters or 0) > 0)
            )
            defenders.append(
                {
                    "ship_id": candidate.ship_id,
                    "name": candidate.name,
                    "hull_id": candidate.hull_id,
                    "distance_to_target": round(distance, 1),
                    "within_warp9_reach": distance <= WARP_9_DISTANCE,
                    "combat_hull": combat_hull,
                    "beam_slots": beam_slots,
                    "tube_slots": tube_slots,
                    "fighter_bays": bays,
                    "torpedoes": torpedoes,
                    "fighters": fighters,
                    "heavy_weapon_ready": heavy_weapon_ready,
                }
            )
    defenders.sort(key=lambda item: item["distance_to_target"])

    reachable_combat = [
        item
        for item in defenders
        if item["within_warp9_reach"] and item["combat_hull"]
    ]
    reachable_heavy = [
        item for item in reachable_combat if item["heavy_weapon_ready"]
    ]

    target_has_starbase = (
        target_planet is not None
        and target_planet.planet_id in base_planet_ids
    )
    risk = "unknown"
    reasons: list[str] = []
    if target_planet is not None:
        if target_eta == 1:
            if not reachable_heavy and not target_has_starbase:
                risk = "critical"
                reasons.append(
                    "Likely target can be reached this host and no heavy-weapon-ready defender is within 81 ly."
                )
            elif not reachable_heavy:
                risk = "high"
                reasons.append(
                    "Likely target can be reached this host; local defense relies on a starbase or beam-only ships."
                )
            else:
                risk = "high"
                reasons.append(
                    "Likely target can be reached this host; at least one torpedo/carrier defender is within 81 ly."
                )
        elif target_eta is not None and target_eta <= 2:
            risk = "high"
            reasons.append("Likely target is within roughly two observed movement turns.")
        else:
            risk = "medium"
            reasons.append("Likely target is identified, but immediate arrival is not established.")

        if len(attack_group) >= 2:
            reasons.append(
                f"{len(attack_group)} same-owner ships have waypoints in the same target area."
            )

    fury_like = "fury" in race_name.casefold() or "fascist" in race_name.casefold()
    double_beams = _setting_bool(
        catalog.settings,
        "fascistdoublebeams",
        "furydoublebeams",
    )
    race_traits = []
    if fury_like:
        race_traits.append(
            {
                "name": "Planet immunity",
                "active": True,
                "basis": "race capability",
            }
        )
        race_traits.append(
            {
                "name": "2× faster beams",
                "active": double_beams,
                "basis": "game setting fascistdoublebeams",
            }
        )

    score_context = _score_context(
        game_id=game_id,
        turn=turn,
        slot_ids={
            slot_id
            for slot_id in (primary_slot_id, subject.owner_id)
            if slot_id is not None
        },
    )

    return {
        "game_id": game_id,
        "turn": turn,
        "ship_id": ship_id,
        "status": "ok",
        "subject": {
            "name": subject.name,
            "owner_slot_id": subject.owner_id,
            "owner_username": owner_slot.username if owner_slot is not None else None,
            "race_id": owner_slot.race_id if owner_slot is not None else None,
            "race_name": race_name,
            "hull_id": subject.hull_id,
            "hull_name": _safe_name(
                hull,
                f"Hull #{subject.hull_id}" if subject.hull_id is not None else "Unknown hull",
            ),
            "observed_mass": observed_mass,
            "minimum_observed_mass": minimum_observed_mass,
            "hull_mass": hull_mass,
            "beam_slots": hull_beam_slots,
            "tube_slots": hull_tube_slots,
            "fighter_bays": hull_bays,
            "info_turn": subject.info_turn,
            "source_batch_id": subject_batch.id,
        },
        "mass_history": mass_history,
        "loadout": {
            "vcr_reveal": vcr_equipment,
            "beam_candidates": beam_candidates,
            "torpedo_candidates": torpedo_candidates,
            "mass_excess_over_bare_hull": (
                observed_mass - hull_mass
                if observed_mass is not None and hull_mass is not None
                else None
            ),
            "mass_caveat": (
                "Observed mass includes hidden fuel, ammunition and cargo; mass constraints can exclude impossible equipment but do not identify a unique loadout."
            ),
        },
        "race_traits": race_traits,
        "target": (
            {
                "planet_id": target_planet.planet_id,
                "name": target_planet.name,
                "x": target_planet.x,
                "y": target_planet.y,
                "waypoint_distance": round(target_waypoint_distance, 1)
                if target_waypoint_distance is not None
                else None,
                "distance_from_ship": round(target_distance, 1)
                if target_distance is not None
                else None,
                "eta_observed_turns": target_eta,
                "confidence": target_confidence,
                "defense_posts": _integer(target_payload or {}, "defense"),
                "has_starbase": target_has_starbase,
            }
            if target_planet is not None
            else None
        ),
        "attack_group": attack_group,
        "defense": {
            "primary_slot_id": primary_slot_id,
            "risk": risk,
            "reasons": reasons,
            "reachable_combat_defenders": len(reachable_combat),
            "reachable_heavy_defenders": len(reachable_heavy),
            "defenders": defenders,
        },
        "military": {
            "subject_owner": score_context.get(subject.owner_id)
            if subject.owner_id is not None
            else None,
            "primary_owner": score_context.get(primary_slot_id),
        },
        "provenance": {
            "analysis_kind": "read_time_inference",
            "facts_unchanged": True,
            "accessible_observer_ids": sorted(accessible_ids),
            "rule_catalog_turn": catalog.observed_turn,
        },
    }
