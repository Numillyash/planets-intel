from typing import Any

from app.services.combat_replay_state import replay_state_map
from app.services.combat_state import combat_state_map
from app.services.event_results import apply_structured_host_evidence


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
