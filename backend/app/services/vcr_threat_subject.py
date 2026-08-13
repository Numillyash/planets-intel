from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_player_slot import GamePlayerSlot
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.intel_access import accessible_intel_accounts


def _integer(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _by_id(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for record in records:
        item_id = _integer(record, "id")
        if item_id is not None:
            result[item_id] = record
    return result


def _name(record: dict[str, Any] | None, fallback: str) -> str:
    if record is not None:
        value = record.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _vcr_ship_side(
    combat: CombatObservation,
    ship_id: int,
) -> tuple[str, dict[str, Any]] | None:
    payload = combat.payload if isinstance(combat.payload, dict) else {}
    for side_name in ("left", "right"):
        side = payload.get(side_name)
        if (
            isinstance(side, dict)
            and side.get("objectid") == ship_id
            and side.get("hullid") not in (None, 0)
        ):
            return side_name, side
    return None


def get_vcr_only_ship_threat_analysis(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    ship_id: int,
) -> dict[str, Any] | None:
    """Build minimal threat context from factual VCR evidence.

    This is intentionally not a ShipObservation substitute. It is a read-time
    analytical subject whose provenance is explicitly VCR combat evidence.
    Position is the combat position; waypoint/warp are unknown unless a direct
    ship observation exists elsewhere.
    """

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
                PrivateObservationBatch.observer_planets_account_id == linked_account_id,
            )
            .order_by(
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
        ).scalars().first()
        if primary_batch is None:
            return None

        rows = list(
            session.execute(
                select(CombatObservation, PrivateObservationBatch)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == CombatObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                    CombatObservation.battle_turn <= turn,
                )
                .order_by(
                    CombatObservation.battle_turn.desc(),
                    CombatObservation.vcr_id.desc(),
                    PrivateObservationBatch.observed_at.desc(),
                    PrivateObservationBatch.id.desc(),
                )
            ).all()
        )

        chosen: tuple[CombatObservation, PrivateObservationBatch, str, dict[str, Any]] | None = None
        for combat, batch in rows:
            match = _vcr_ship_side(combat, ship_id)
            if match is None:
                continue
            side_name, side = match
            chosen = (combat, batch, side_name, side)
            break

        if chosen is None:
            return None

        slots = list(
            session.execute(
                select(GamePlayerSlot).where(GamePlayerSlot.game_id == game_id)
            ).scalars().all()
        )

    combat, batch, side_name, side = chosen
    slot_by_id = {slot.slot_id: slot for slot in slots}
    primary_slot_id = primary_batch.source_player_slot_id

    owner_id = combat.left_owner_id if side_name == "left" else combat.right_owner_id
    if owner_id is None:
        owner_id = _integer(
            combat.payload,
            "leftownerid" if side_name == "left" else "rightownerid",
        )

    hull_id = _integer(side, "hullid")
    hulls = _by_id(catalog.hulls)
    beams = _by_id(catalog.beams)
    torpedos = _by_id(catalog.torpedos)
    races = _by_id(catalog.races)

    hull = hulls.get(hull_id) if hull_id is not None else None
    owner_slot = slot_by_id.get(owner_id) if owner_id is not None else None
    race = races.get(owner_slot.race_id) if owner_slot is not None else None

    beam_id = _integer(side, "beamid")
    torpedo_id = _integer(side, "torpedoid")
    beam_count = _integer(side, "beamcount")
    launcher_count = _integer(side, "launchercount")
    observed_mass = _integer(side, "mass")
    hull_mass = _integer(hull, "mass") if hull is not None else None
    hull_beam_slots = _integer(hull, "beams") if hull is not None else None
    hull_tube_slots = _integer(hull, "launchers") if hull is not None else None
    hull_bays = _integer(hull, "fighterbays") if hull is not None else None

    beam_candidates: list[dict[str, Any]] = []
    if beam_id is not None and beam_id > 0:
        beam = beams.get(beam_id)
        beam_mass = _integer(beam, "mass") if beam is not None else None
        beam_candidates.append(
            {
                "id": beam_id,
                "name": _name(beam, f"Beam #{beam_id}"),
                "tech_level": _integer(beam, "techlevel") if beam is not None else None,
                "mass_each": beam_mass,
                "minimum_hull_plus_beams_mass": (
                    hull_mass + hull_beam_slots * beam_mass
                    if hull_mass is not None
                    and hull_beam_slots is not None
                    and beam_mass is not None
                    else None
                ),
            }
        )

    torpedo_candidates: list[dict[str, Any]] = []
    if torpedo_id is not None and torpedo_id > 0:
        torpedo = torpedos.get(torpedo_id)
        torpedo_candidates.append(
            {
                "id": torpedo_id,
                "name": _name(torpedo, f"Torpedo #{torpedo_id}"),
                "tech_level": _integer(torpedo, "techlevel") if torpedo is not None else None,
            }
        )

    race_name = _name(
        race,
        f"Race #{owner_slot.race_id}" if owner_slot is not None else "Unknown race",
    )

    vcr_reveal = {
        "battle_turn": combat.battle_turn,
        "vcr_id": combat.vcr_id,
        "batch_id": batch.id,
        "beam_id": beam_id,
        "beam_count": beam_count,
        "torpedo_id": torpedo_id,
        "launcher_count": launcher_count,
        "torpedoes": _integer(side, "torpedos"),
        "fighters": _integer(side, "fighters"),
        "crew": _integer(side, "crew"),
        "damage": _integer(side, "damage"),
        "mass": observed_mass,
    }

    return {
        "game_id": game_id,
        "turn": turn,
        "ship_id": ship_id,
        "status": "ok",
        "subject": {
            "name": side.get("name") if isinstance(side.get("name"), str) else None,
            "owner_slot_id": owner_id,
            "owner_username": owner_slot.username if owner_slot is not None else None,
            "race_id": owner_slot.race_id if owner_slot is not None else None,
            "race_name": race_name,
            "hull_id": hull_id,
            "hull_name": _name(hull, f"Hull #{hull_id}" if hull_id is not None else "Unknown hull"),
            "observed_mass": observed_mass,
            "minimum_observed_mass": observed_mass,
            "hull_mass": hull_mass,
            "beam_slots": hull_beam_slots,
            "tube_slots": hull_tube_slots,
            "fighter_bays": hull_bays,
            "info_turn": combat.battle_turn,
            "source_batch_id": batch.id,
            "evidence_basis": "vcr_combat_observation",
            "combat_x": combat.x,
            "combat_y": combat.y,
        },
        "mass_history": (
            [{"turn": combat.battle_turn, "mass": observed_mass}]
            if observed_mass is not None
            else []
        ),
        "loadout": {
            "vcr_reveal": vcr_reveal,
            "beam_candidates": beam_candidates,
            "torpedo_candidates": torpedo_candidates,
            "mass_excess_over_bare_hull": (
                observed_mass - hull_mass
                if observed_mass is not None and hull_mass is not None
                else None
            ),
            "mass_caveat": (
                "Subject is known from factual VCR combat evidence. VCR mass is combat-start mass; "
                "waypoint, warp and normal scan-only fields are not inferred."
            ),
        },
        "race_traits": [],
        "target": None,
        "attack_group": [],
        "defense": {
            "primary_slot_id": primary_slot_id,
            "risk": "unknown",
            "reasons": [
                "Ship is known from factual VCR combat evidence; movement objective is not inferred without a direct ship observation."
            ],
            "reachable_combat_defenders": 0,
            "reachable_heavy_defenders": 0,
            "defenders": [],
        },
        "military": {
            "subject_owner": None,
            "primary_owner": None,
        },
        "provenance": {
            "analysis_kind": "read_time_inference",
            "facts_unchanged": True,
            "accessible_observer_ids": sorted(accessible_ids),
            "rule_catalog_turn": catalog.observed_turn,
            "subject_basis": "vcr_combat_observation",
            "vcr_id": combat.vcr_id,
        },
    }
