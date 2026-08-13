from typing import Any

from app.services.combat_state import latest_ship_combat_state
from app.services.threat_analysis import get_ship_threat_analysis


def get_ship_threat_analysis_with_post_state(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    ship_id: int,
) -> dict[str, Any] | None:
    result = get_ship_threat_analysis(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        ship_id=ship_id,
    )
    if result is None or result.get("status") != "ok":
        return result

    state = latest_ship_combat_state(
        user_id=user_id,
        game_id=game_id,
        ship_id=ship_id,
        through_turn=turn,
    )

    loadout = result.get("loadout")
    if isinstance(loadout, dict):
        vcr = loadout.get("vcr_reveal")
        if isinstance(vcr, dict):
            vcr["combat_start_torpedoes"] = vcr.get("torpedoes")
            vcr["combat_start_fighters"] = vcr.get("fighters")
            vcr["post_combat_torpedoes"] = (
                state.post_combat_torpedoes if state is not None else None
            )
            vcr["post_combat_fighters"] = (
                state.post_combat_fighters if state is not None else None
            )
            vcr["post_combat_turn"] = state.turn if state is not None else None
            vcr["post_combat_vcr_id"] = state.vcr_id if state is not None else None
            vcr["post_combat_source"] = (
                "analyst_confirmed_vcr_review" if state is not None else None
            )

    result["current_combat_state"] = (
        {
            "turn": state.turn,
            "vcr_id": state.vcr_id,
            "post_combat_torpedoes": state.post_combat_torpedoes,
            "post_combat_fighters": state.post_combat_fighters,
            "source": "analyst_confirmed_vcr_review",
        }
        if state is not None
        else None
    )
    return result
