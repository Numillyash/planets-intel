from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.score_observation import ScoreObservation
from app.models.ship_observation import ShipObservation
from app.services.intel_access import accessible_intel_accounts


COST_MC_KEYS = ("megacredits", "mc", "costmc", "megacreditcost")
COST_DUR_KEYS = ("duranium", "dur", "costduranium", "duraniumcost")
COST_TRI_KEYS = ("tritanium", "tri", "costtritanium", "tritaniumcost")
COST_MOLY_KEYS = ("molybdenum", "moly", "costmolybdenum", "molybdenumcost")


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


def _name(record: dict[str, Any] | None, fallback: str) -> str:
    if record is not None:
        value = record.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _by_id(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for record in records:
        item_id = _integer(record, "id")
        if item_id is not None:
            result[item_id] = record
    return result


def _effective_turn(observation: ShipObservation, batch: PrivateObservationBatch) -> int:
    if observation.info_turn is not None and observation.info_turn > 0:
        return observation.info_turn
    return batch.turn


def _component_score(record: dict[str, Any] | None) -> int | None:
    mc = _integer(record, *COST_MC_KEYS)
    dur = _integer(record, *COST_DUR_KEYS)
    tri = _integer(record, *COST_TRI_KEYS)
    moly = _integer(record, *COST_MOLY_KEYS)
    if mc is None or dur is None or tri is None or moly is None:
        return None
    return mc + 5 * (dur + tri + moly)


def _latest_subject(
    rows: list[tuple[ShipObservation, PrivateObservationBatch]],
    turn: int,
) -> tuple[ShipObservation, PrivateObservationBatch] | None:
    exact = [pair for pair in rows if pair[1].turn == turn]
    if not exact:
        return None
    exact.sort(
        key=lambda pair: (
            _effective_turn(pair[0], pair[1]),
            pair[1].observed_at,
            pair[1].id,
        )
    )
    return exact[-1]


def _latest_vcr_equipment(
    combats: list[tuple[CombatObservation, PrivateObservationBatch]],
    ship_id: int,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for combat, batch in combats:
        payload = combat.payload if isinstance(combat.payload, dict) else {}
        for side_name in ("left", "right"):
            side = payload.get(side_name)
            if not isinstance(side, dict) or side.get("objectid") != ship_id:
                continue
            candidates.append(
                {
                    "vcr_id": combat.vcr_id,
                    "battle_turn": combat.battle_turn,
                    "batch_id": batch.id,
                    "beam_id": _integer(side, "beamid"),
                    "torpedo_id": _integer(side, "torpedoid"),
                    "beam_count": _integer(side, "beamcount"),
                    "launcher_count": _integer(side, "launchercount"),
                }
            )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item["battle_turn"], item["vcr_id"], item["batch_id"]))
    return candidates[-1]


def _score_history(
    *, game_id: int, slot_id: int, through_turn: int,
) -> tuple[ScoreObservation | None, ScoreObservation | None]:
    with SessionLocal() as session:
        rows = list(
            session.execute(
                select(ScoreObservation)
                .where(
                    ScoreObservation.game_id == game_id,
                    ScoreObservation.slot_id == slot_id,
                    ScoreObservation.turn <= through_turn,
                )
                .order_by(ScoreObservation.turn)
            ).scalars().all()
        )
    if not rows:
        return None, None
    return rows[-1], rows[-2] if len(rows) >= 2 else None


def _fuel_prior_points(fill_ratio: float | None) -> int:
    if fill_ratio is None:
        return 0
    if fill_ratio >= 0.95:
        return 30
    if fill_ratio >= 0.90:
        return 24
    if fill_ratio >= 0.80:
        return 14
    if fill_ratio >= 0.65:
        return 5
    return -10


def _military_fit_points(residual: int | None) -> int:
    if residual is None:
        return 0
    if residual < -500:
        return -45
    if residual < -200:
        return -25
    if residual < 0:
        return -5
    if residual <= 100:
        return 50
    if residual <= 300:
        return 42
    if residual <= 600:
        return 32
    if residual <= 1000:
        return 20
    if residual <= 1600:
        return 8
    return 0


def _evidence_grade(points: int, uses_military_delta: bool) -> str:
    if uses_military_delta and points >= 68:
        return "strong"
    if points >= 45:
        return "moderate"
    return "weak"


def get_ship_loadout_inference(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    ship_id: int,
) -> dict[str, Any] | None:
    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = {account.id for account in accessible}
    if linked_account_id not in accessible_ids or not accessible_ids:
        return None

    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()
        if catalog is None:
            return {"status": "catalog_missing", "detail": "Game rule catalog is not stored yet."}

        rows = list(
            session.execute(
                select(ShipObservation, PrivateObservationBatch)
                .join(PrivateObservationBatch, PrivateObservationBatch.id == ShipObservation.batch_id)
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.turn <= turn,
                    PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                    ShipObservation.ship_id == ship_id,
                )
            ).all()
        )
        current_rows = list(
            session.execute(
                select(ShipObservation, PrivateObservationBatch)
                .join(PrivateObservationBatch, PrivateObservationBatch.id == ShipObservation.batch_id)
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.turn == turn,
                    PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                )
            ).all()
        )
        combat_rows = list(
            session.execute(
                select(CombatObservation, PrivateObservationBatch)
                .join(PrivateObservationBatch, PrivateObservationBatch.id == CombatObservation.batch_id)
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                    CombatObservation.battle_turn <= turn,
                )
            ).all()
        )

    subject_pair = _latest_subject(rows, turn)
    if subject_pair is None:
        return None
    subject, subject_batch = subject_pair
    if subject.owner_id is None or subject.hull_id is None:
        return None

    hulls = _by_id(catalog.hulls)
    beams = _by_id(catalog.beams)
    torpedos = _by_id(catalog.torpedos)
    engines = _by_id(catalog.engines)
    hull = hulls.get(subject.hull_id)
    if hull is None:
        return None

    payload = subject.payload if isinstance(subject.payload, dict) else {}
    observed_mass = _integer(payload, "mass")
    hull_mass = _integer(hull, "mass")
    fuel_capacity = _integer(hull, "fuel", "fueltank", "fuelcapacity")
    cargo_capacity = _integer(hull, "cargo", "cargocapacity")
    engine_count = _integer(hull, "engines") or 0
    beam_slots = _integer(hull, "beams") or 0
    tube_slots = _integer(hull, "launchers", "tubes") or 0

    observed_turns = sorted({_effective_turn(obs, batch) for obs, batch in rows})
    first_observed_turn = observed_turns[0] if observed_turns else turn
    vcr = _latest_vcr_equipment(combat_rows, ship_id)
    revealed_beam = vcr.get("beam_id") if vcr is not None else None
    revealed_torpedo = vcr.get("torpedo_id") if vcr is not None else None

    current_score, previous_score = _score_history(
        game_id=game_id,
        slot_id=subject.owner_id,
        through_turn=turn,
    )
    military_delta = (
        current_score.military_score - previous_score.military_score
        if current_score is not None and previous_score is not None else None
    )
    warship_delta = (
        current_score.capital_ships - previous_score.capital_ships
        if current_score is not None and previous_score is not None else None
    )
    freighter_delta = (
        current_score.freighters - previous_score.freighters
        if current_score is not None and previous_score is not None else None
    )

    first_score, first_previous_score = _score_history(
        game_id=game_id,
        slot_id=subject.owner_id,
        through_turn=first_observed_turn,
    )
    first_score_exact = first_score is not None and first_score.turn == first_observed_turn
    candidate_military_delta = (
        first_score.military_score - first_previous_score.military_score
        if first_score_exact and first_previous_score is not None
        else None
    )
    candidate_warship_delta = (
        first_score.capital_ships - first_previous_score.capital_ships
        if first_score_exact and first_previous_score is not None
        else None
    )
    candidate_freighter_delta = (
        first_score.freighters - first_previous_score.freighters
        if first_score_exact and first_previous_score is not None
        else None
    )
    conditional_build_link = bool(
        candidate_warship_delta == 1
        and candidate_military_delta is not None
        and candidate_military_delta > 0
    )

    owner_latest: dict[int, tuple[ShipObservation, PrivateObservationBatch]] = {}
    for candidate, batch in current_rows:
        if candidate.owner_id != subject.owner_id:
            continue
        current = owner_latest.get(candidate.ship_id)
        if current is None or (
            _effective_turn(candidate, batch), batch.observed_at, batch.id
        ) > (
            _effective_turn(current[0], current[1]), current[1].observed_at, current[1].id
        ):
            owner_latest[candidate.ship_id] = (candidate, batch)

    visible_warships = 0
    visible_noncombat = 0
    for candidate, _batch in owner_latest.values():
        candidate_hull = hulls.get(candidate.hull_id) if candidate.hull_id is not None else None
        candidate_beams = _integer(candidate_hull, "beams") or 0
        candidate_tubes = _integer(candidate_hull, "launchers", "tubes") or 0
        candidate_bays = _integer(candidate_hull, "fighterbays") or 0
        if candidate_beams > 0 or candidate_tubes > 0 or candidate_bays > 0:
            visible_warships += 1
        else:
            visible_noncombat += 1

    hull_score = _component_score(hull)
    candidates: list[dict[str, Any]] = []
    engine_items = list(sorted(engines.items())) if engine_count > 0 else [(None, None)]
    beam_items = list(sorted(beams.items())) if beam_slots > 0 else [(None, None)]
    torpedo_items = list(sorted(torpedos.items())) if tube_slots > 0 else [(None, None)]

    for engine_id, engine in engine_items:
        engine_score = _component_score(engine)
        for beam_id, beam in beam_items:
            if isinstance(revealed_beam, int) and revealed_beam > 0 and beam_id != revealed_beam:
                continue
            beam_mass = _integer(beam, "mass") if beam is not None else 0
            beam_score = _component_score(beam)
            for torpedo_id, torpedo in torpedo_items:
                if isinstance(revealed_torpedo, int) and revealed_torpedo > 0 and torpedo_id != revealed_torpedo:
                    continue
                tube_mass = _integer(torpedo, "mass", "launchermass", "tubemass") if torpedo is not None else 0
                tube_score = _component_score(torpedo)

                weapon_mass = None
                max_fuel = None
                fill_ratio = None
                full_tank_shortfall = None
                if observed_mass is not None and hull_mass is not None and beam_mass is not None and tube_mass is not None:
                    weapon_mass = beam_slots * beam_mass + tube_slots * tube_mass
                    unassigned = observed_mass - hull_mass - weapon_mass
                    if unassigned < 0:
                        continue
                    if fuel_capacity is not None and fuel_capacity > 0:
                        max_fuel = min(fuel_capacity, unassigned)
                        fill_ratio = max_fuel / fuel_capacity
                        full_tank_shortfall = max(0, fuel_capacity - unassigned)

                build_score = None
                if (
                    hull_score is not None
                    and (engine_count == 0 or engine_score is not None)
                    and (beam_slots == 0 or beam_score is not None)
                    and (tube_slots == 0 or tube_score is not None)
                ):
                    build_score = hull_score
                    if engine_score is not None:
                        build_score += engine_count * engine_score
                    if beam_score is not None:
                        build_score += beam_slots * beam_score
                    if tube_score is not None:
                        build_score += tube_slots * tube_score

                residual = (
                    candidate_military_delta - build_score
                    if conditional_build_link
                    and candidate_military_delta is not None
                    and build_score is not None
                    else None
                )
                points = _fuel_prior_points(fill_ratio)
                if conditional_build_link:
                    points += _military_fit_points(residual)
                if vcr is not None:
                    points += 35

                candidates.append(
                    {
                        "engine_id": engine_id,
                        "engine_name": _name(engine, "No engine") if engine is not None else None,
                        "engine_tech": _integer(engine, "techlevel", "tech") if engine is not None else None,
                        "beam_id": beam_id,
                        "beam_name": _name(beam, "No beams") if beam is not None else None,
                        "beam_tech": _integer(beam, "techlevel", "tech") if beam is not None else None,
                        "torpedo_id": torpedo_id,
                        "torpedo_name": _name(torpedo, "No tubes") if torpedo is not None else None,
                        "torpedo_tech": _integer(torpedo, "techlevel", "tech") if torpedo is not None else None,
                        "weapon_mass": weapon_mass,
                        "max_fuel_if_no_cargo_or_ammo": max_fuel,
                        "max_fuel_fill_ratio": round(fill_ratio, 4) if fill_ratio is not None else None,
                        "full_tank_shortfall": full_tank_shortfall,
                        "build_military_score": build_score,
                        "military_delta_residual": residual,
                        "evidence_points": points,
                        "evidence_grade": _evidence_grade(points, conditional_build_link),
                    }
                )

    candidates.sort(
        key=lambda item: (
            item["evidence_points"],
            item["max_fuel_fill_ratio"] if item["max_fuel_fill_ratio"] is not None else -1,
            -(abs(item["military_delta_residual"]) if item["military_delta_residual"] is not None else 10**9),
        ),
        reverse=True,
    )

    return {
        "status": "ok",
        "game_id": game_id,
        "turn": turn,
        "ship_id": ship_id,
        "subject": {
            "name": subject.name,
            "owner_slot_id": subject.owner_id,
            "hull_id": subject.hull_id,
            "hull_name": _name(hull, f"Hull #{subject.hull_id}"),
            "observed_mass": observed_mass,
            "hull_mass": hull_mass,
            "fuel_capacity": fuel_capacity,
            "cargo_capacity": cargo_capacity,
            "engine_count": engine_count,
            "beam_slots": beam_slots,
            "tube_slots": tube_slots,
            "first_observed_turn": first_observed_turn,
        },
        "military_ledger": {
            "current_turn": current_score.turn if current_score is not None else None,
            "military_score": current_score.military_score if current_score is not None else None,
            "military_delta": military_delta,
            "warships": current_score.capital_ships if current_score is not None else None,
            "warship_delta": warship_delta,
            "freighters": current_score.freighters if current_score is not None else None,
            "freighter_delta": freighter_delta,
            "visible_warships": visible_warships,
            "visible_noncombat_ships": visible_noncombat,
            "candidate_build_turn": first_observed_turn,
            "candidate_build_military_delta": candidate_military_delta,
            "candidate_build_warship_delta": candidate_warship_delta,
            "candidate_build_freighter_delta": candidate_freighter_delta,
            "conditional_build_link": conditional_build_link,
        },
        "vcr_reveal": vcr,
        "assumptions": {
            "near_full_departure_fuel": "soft_prior",
            "selected_ship_is_new_build": "conditional" if conditional_build_link else "not_established",
            "military_residual": "Residual may include loaded ammunition, defenses, minefields, and other fleet changes.",
            "first_seen_caveat": "First factual observation is not proof of construction; fog of war can reveal an older ship for the first time.",
            "historical_score_link": (
                f"Candidate score delta is taken from T{first_observed_turn}, the first factual sighting turn."
                if conditional_build_link
                else "No unique +1 public warship delta is established on the first factual sighting turn."
            ),
        },
        "ranked_candidates": candidates[:12],
        "provenance": {
            "analysis_kind": "read_time_inference",
            "facts_unchanged": True,
            "rule_catalog_turn": catalog.observed_turn,
            "source_batch_id": subject_batch.id,
        },
    }
