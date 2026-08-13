from typing import Any

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
    """Combine immutable VCR facts with separately stored post-combat observations.

    Raw VCR ``torpedos``/``fighters`` values are combat-start state. They are
    never rewritten. Analyst-confirmed post-combat state is kept in the
    dedicated combat_state_observations table and exposed alongside it.
    """

    result = apply_structured_host_evidence(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        result=result,
    )
    states = combat_state_map(
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

            # Preserve backward-compatible raw fields while giving them an
            # unambiguous semantic name for new clients.
            equipment["combat_start_torpedoes"] = equipment.get("torpedoes")
            equipment["combat_start_fighters"] = equipment.get("fighters")

            post_state = states.get((vcr_id, ship_id))
            equipment["post_combat_torpedoes"] = (
                post_state.post_combat_torpedoes if post_state is not None else None
            )
            equipment["post_combat_fighters"] = (
                post_state.post_combat_fighters if post_state is not None else None
            )
            equipment["post_combat_source"] = (
                "analyst_confirmed_vcr_review" if post_state is not None else None
            )

    return result
