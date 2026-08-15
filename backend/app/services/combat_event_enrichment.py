from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.combat_replay_state import replay_state_map
from app.services.combat_state import combat_state_map
from app.services.event_results import apply_structured_host_evidence
from app.services.intel_access import accessible_intel_accounts


def _integer(record: dict[str, Any], key: str) -> int | None:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _combat_equipment(side: dict[str, Any]) -> dict[str, Any]:
    """Extract immutable combat-start equipment from one raw Nu VCR side."""
    return {
        "beam_id": _integer(side, "beamid"),
        "beam_count": _integer(side, "beamcount"),
        "launcher_count": _integer(side, "launchercount"),
        "bay_count": _integer(side, "baycount"),
        "torpedo_id": _integer(side, "torpedoid"),
        "torpedoes": _integer(side, "torpedos"),
        "fighters": _integer(side, "fighters"),
        "shield": _integer(side, "shield"),
        "damage": _integer(side, "damage"),
        "crew": _integer(side, "crew"),
        "mass": _integer(side, "mass"),
        "race_id": _integer(side, "raceid"),
        "evidence_basis": "vcr_combat_observation",
    }


def _attach_factual_vcr_equipment(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    result: dict[str, Any],
) -> None:
    """Attach factual combat-start equipment without mutating observations.

    Combat events are deduplicated across all intel sources accessible to the
    current dashboard user.  For each VCR we choose the freshest accessible
    raw observation and expose its side equipment as a read-time evidence
    object.  This does not turn combat-time state into a current ship fact.
    """
    accessible = accessible_intel_accounts(user_id=user_id)
    accessible_ids = {account.id for account in accessible}
    if linked_account_id not in accessible_ids or not accessible_ids:
        return

    with SessionLocal() as session:
        rows = session.execute(
            select(CombatObservation, PrivateObservationBatch)
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == CombatObservation.batch_id,
            )
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id.in_(accessible_ids),
                CombatObservation.battle_turn == turn,
            )
            .order_by(
                CombatObservation.vcr_id,
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
        ).all()

    by_vcr: dict[int, CombatObservation] = {}
    for combat, _batch in rows:
        by_vcr.setdefault(combat.vcr_id, combat)

    events = result.get("events")
    if not isinstance(events, list):
        return

    for event in events:
        if not isinstance(event, dict):
            continue
        vcr_id = event.get("vcr_id")
        sides = event.get("sides")
        combat = by_vcr.get(vcr_id) if isinstance(vcr_id, int) else None
        if combat is None or not isinstance(sides, list):
            continue

        raw_payload = combat.payload if isinstance(combat.payload, dict) else {}
        raw_sides = {
            name: raw_payload.get(name)
            for name in ("left", "right")
        }

        for side in sides:
            if not isinstance(side, dict) or side.get("object_kind") != "ship":
                continue
            side_name = side.get("side")
            raw_side = raw_sides.get(side_name) if isinstance(side_name, str) else None
            if not isinstance(raw_side, dict):
                continue

            # Protect against malformed/mismatched raw rows before attaching
            # equipment to the normalized event side.
            normalized_object_id = side.get("object_id")
            raw_object_id = _integer(raw_side, "objectid")
            if (
                isinstance(normalized_object_id, int)
                and raw_object_id is not None
                and raw_object_id != normalized_object_id
            ):
                continue

            side["combat_equipment"] = _combat_equipment(raw_side)


def enrich_combat_events(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Combine immutable VCR facts with separate post-combat evidence.

    Raw VCR ``torpedos``/``fighters`` values remain combat-start facts.
    Deterministic replay is exposed as derived evidence. Analyst-confirmed
    review is stored separately and takes precedence for the same VCR ship.
    """

    _attach_factual_vcr_equipment(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        result=result,
    )

    result = apply_structured_host_evidence(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        result=result,
    )
    analyst_states = combat_state_map(
        user_id=user_id,
        game_id=game_id,
        turn=turn,
    )
    replay_states = replay_state_map(
        user_id=user_id,
        game_id=game_id,
        turn=turn,
    )

    events = result.get("events")
    if not isinstance(events, list):
        return result

    for event in events:
        if not isinstance(event, dict):
            continue
        vcr_id = event.get("vcr_id")
        sides = event.get("sides")
        if not isinstance(vcr_id, int) or not isinstance(sides, list):
            continue

        for side in sides:
            if not isinstance(side, dict) or side.get("object_kind") != "ship":
                continue
            ship_id = side.get("object_id")
            equipment = side.get("combat_equipment")
            if not isinstance(ship_id, int) or not isinstance(equipment, dict):
                continue

            equipment["combat_start_torpedoes"] = equipment.get("torpedoes")
            equipment["combat_start_fighters"] = equipment.get("fighters")

            analyst = analyst_states.get((vcr_id, ship_id))
            replay = replay_states.get((vcr_id, ship_id))

            equipment["replay_post_combat_torpedoes"] = (
                replay.get("post_combat_torpedoes") if replay is not None else None
            )
            equipment["replay_post_combat_fighters"] = (
                replay.get("post_combat_fighters") if replay is not None else None
            )
            equipment["replay_post_combat_shield"] = (
                replay.get("post_combat_shield") if replay is not None else None
            )
            equipment["replay_post_combat_damage"] = (
                replay.get("post_combat_damage") if replay is not None else None
            )
            equipment["replay_post_combat_crew"] = (
                replay.get("post_combat_crew") if replay is not None else None
            )
            equipment["replay_engine"] = replay.get("engine") if replay is not None else None
            equipment["replay_basis"] = replay.get("basis") if replay is not None else None

            if analyst is not None:
                equipment["post_combat_torpedoes"] = analyst.post_combat_torpedoes
                equipment["post_combat_fighters"] = analyst.post_combat_fighters
                equipment["post_combat_source"] = "analyst_confirmed_vcr_review"
                if replay is not None:
                    replay_torps = replay.get("post_combat_torpedoes")
                    replay_fighters = replay.get("post_combat_fighters")
                    equipment["replay_matches_analyst"] = (
                        (analyst.post_combat_torpedoes is None or replay_torps == analyst.post_combat_torpedoes)
                        and (analyst.post_combat_fighters is None or replay_fighters == analyst.post_combat_fighters)
                    )
                else:
                    equipment["replay_matches_analyst"] = None
            elif replay is not None:
                equipment["post_combat_torpedoes"] = replay.get("post_combat_torpedoes")
                equipment["post_combat_fighters"] = replay.get("post_combat_fighters")
                equipment["post_combat_source"] = "deterministic_vcr_replay"
                equipment["replay_matches_analyst"] = None
            else:
                equipment["post_combat_torpedoes"] = None
                equipment["post_combat_fighters"] = None
                equipment["post_combat_source"] = None
                equipment["replay_matches_analyst"] = None

    return result
